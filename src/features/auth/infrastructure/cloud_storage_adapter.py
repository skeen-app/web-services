import os
from google.cloud import storage
from google.cloud.exceptions import NotFound
from src.core.logger import get_logger

logger = get_logger(__name__)

# Mapping from MIME type to file extension
_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# Every extension the upload pipeline could have produced. The delete
# sweep walks all of them because the bucket holds at most one of these
# per user (re-uploads with a different MIME would have left stale blobs
# under the previous extension, so we tidy those up too).
_KNOWN_EXTS: tuple[str, ...] = tuple(_MIME_TO_EXT.values())


class CloudStorageAdapter:
    """Infrastructure adapter for Google Cloud Storage — profile photo uploads."""

    def __init__(self, client: storage.Client):
        self.client = client
        self.bucket_name = os.getenv("GCS_PROFILE_PHOTOS_BUCKET", "skeen-profile-photos")

    async def upload_profile_photo(self, user_id: str, file_content: bytes, content_type: str) -> str:
        """
        Upload profile photo bytes to Cloud Storage and return the public URL.
        The object path follows: profiles/{user_id}.{ext}
        Re-uploading overwrites the previous photo automatically.
        """
        ext = _MIME_TO_EXT.get(content_type, "jpg")
        blob_path = f"profiles/{user_id}.{ext}"

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_path)
            blob.cache_control = "no-cache, max-age=0"
            blob.upload_from_string(file_content, content_type=content_type)

            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"
            logger.info(f"CloudStorageAdapter: Uploaded profile photo for user {user_id} -> {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"CloudStorageAdapter: Failed to upload photo for user {user_id}. Error: {e}", exc_info=True)
            raise

    async def delete_profile_photo(self, user_id: str) -> bool:
        """Sweep every profile-photo blob owned by this user.

        Returns ``True`` when at least one blob was actually deleted,
        ``False`` when nothing was found (idempotent — re-running after a
        successful delete is a safe no-op). Individual failures are
        logged as warnings and never raised; the caller (the service
        layer) decides what to do with a partial sweep — for our current
        flow we still clear Firestore so the UI matches the user's
        intent.
        """
        bucket = self.client.bucket(self.bucket_name)
        deleted_any = False
        for ext in _KNOWN_EXTS:
            blob_path = f"profiles/{user_id}.{ext}"
            blob = bucket.blob(blob_path)
            try:
                blob.delete()
                deleted_any = True
                logger.info(
                    f"CloudStorageAdapter: Deleted profile photo blob {blob_path}"
                )
            except NotFound:
                # Expected for every extension the user never uploaded.
                continue
            except Exception as e:
                logger.warning(
                    f"CloudStorageAdapter: Best-effort delete failed for {blob_path}. "
                    f"Continuing with the remaining extensions. Error: {e}"
                )
        return deleted_any
