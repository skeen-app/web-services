import time

from fastapi import HTTPException, status
from src.features.auth.domain.entities import IStorageRepository, IUserRepository
from src.core.logger import get_logger

logger = get_logger(__name__)

# Allowed MIME types and their matching magic byte signatures
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

MAGIC_BYTES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png":  [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],  # WebP starts with RIFF; "WEBP" appears at offset 8
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class ProfilePhotoService:
    """Application Service (Use Case) — orchestrates profile photo upload with security validations."""

    def __init__(self, storage_repo: IStorageRepository, user_repo: IUserRepository):
        self.storage_repo = storage_repo
        self.user_repo = user_repo

    async def upload_profile_photo(self, user_id: str, file_content: bytes, filename: str, content_type: str) -> str:
        """
        Validate, upload, and persist a user's profile photo.
        Returns the public URL of the uploaded image.
        """
        logger.info(f"ProfilePhotoService: Starting upload for user {user_id}, file={filename}, content_type={content_type}")

        # --- Security Validations ---
        self._validate_content_type(content_type)
        self._validate_extension(filename)
        self._validate_file_size(file_content)
        self._validate_magic_bytes(file_content, content_type)

        # --- Upload to Cloud Storage ---
        public_url = await self.storage_repo.upload_profile_photo(user_id, file_content, content_type)
        logger.info(f"ProfilePhotoService: Photo uploaded to storage for user {user_id}")

        # --- Persist URL in Firestore ---
        await self.user_repo.update_avatar_url(user_id, public_url)
        logger.info(f"ProfilePhotoService: Photo URL persisted in database for user {user_id}")

        return public_url

    async def delete_profile_photo(self, user_id: str) -> tuple[bool, int]:
        """Remove the user's profile photo — Cloud Storage blob + the
        ``avatarUrl`` field on the Firestore profile.

        Returns ``(deleted, deletedAt)``:
            • ``deleted = True`` when the user had a photo at call time
              and we successfully cleared the Firestore record. The GCS
              blob deletion is best-effort: if the network blip leaves
              a stale blob behind we still consider the operation a
              success because the source of truth for the UI (the
              Firestore ``avatarUrl``) was reset.
            • ``deleted = False`` when the user had no photo to begin
              with (idempotent — the mobile client can retry safely).
              ``deletedAt`` is ``0`` in that case so callers can use it
              as a "no-op marker" without branching on the boolean.
        """
        logger.info(f"ProfilePhotoService: Delete requested for user {user_id}")

        user = await self.user_repo.get_user(user_id)
        if user is None:
            # The endpoint authenticates the caller via Firebase before
            # invoking us, so a missing Firestore profile here is an
            # inconsistency worth flagging — surface as 404 so the
            # client can recover (re-run profile completion).
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found.",
            )

        if not user.avatarUrl:
            logger.info(
                f"ProfilePhotoService: Nothing to delete for user {user_id} "
                f"(avatarUrl already empty)"
            )
            return False, 0

        # Best-effort GCS sweep — mirrors the delete-scan pattern. A
        # warning is logged when nothing is found OR when the underlying
        # client raises a transient error; we still clear Firestore.
        try:
            removed_any = await self.storage_repo.delete_profile_photo(user_id)
            if not removed_any:
                logger.warning(
                    f"ProfilePhotoService: avatarUrl was set but no blob "
                    f"existed in storage for user {user_id} — clearing "
                    f"Firestore anyway"
                )
        except Exception as e:
            logger.warning(
                f"ProfilePhotoService: Storage deletion failed for user "
                f"{user_id}, continuing with Firestore cleanup. Error: {e}"
            )

        await self.user_repo.update_avatar_url(user_id, None)
        deleted_at = int(time.time())
        logger.info(
            f"ProfilePhotoService: Profile photo cleared for user {user_id} "
            f"at {deleted_at}"
        )
        return True, deleted_at

    # ──────────────────────────── validators ────────────────────────────

    @staticmethod
    def _validate_content_type(content_type: str) -> None:
        if content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(f"ProfilePhotoService: Rejected content_type={content_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}",
            )

    @staticmethod
    def _validate_extension(filename: str) -> None:
        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        ext = ""
        if filename and "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
            ext = f".{ext}"
        if ext not in allowed_extensions:
            logger.warning(f"ProfilePhotoService: Rejected file extension={ext} for file={filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension. Allowed: {', '.join(allowed_extensions)}",
            )

    @staticmethod
    def _validate_file_size(file_content: bytes) -> None:
        if len(file_content) > MAX_FILE_SIZE:
            size_mb = round(len(file_content) / (1024 * 1024), 2)
            logger.warning(f"ProfilePhotoService: Rejected oversized file ({size_mb} MB)")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large ({size_mb} MB). Maximum allowed: 5 MB.",
            )

    @staticmethod
    def _validate_magic_bytes(file_content: bytes, content_type: str) -> None:
        """Verify that the first bytes of the file match the declared content type."""
        signatures = MAGIC_BYTES.get(content_type, [])
        if not signatures:
            return  # No signature check available for this type

        for sig in signatures:
            if file_content[:len(sig)] == sig:
                # Additional check for WebP: byte 8-12 must be "WEBP"
                if content_type == "image/webp" and file_content[8:12] != b"WEBP":
                    break  # Falls through to the rejection below
                return  # Valid magic bytes

        logger.warning(f"ProfilePhotoService: Magic bytes mismatch for declared content_type={content_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match declared type. The file may be corrupted or disguised.",
        )
