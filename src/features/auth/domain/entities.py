from pydantic import BaseModel
from typing import Protocol


class FirebaseIdentity(BaseModel):
    """Result of decoding a Firebase ID token. Carries enough metadata for
    the auth service to upsert a profile on first federated sign-in.

    ``provider_id`` is the Firebase ``sign_in_provider`` claim — examples:
    ``google.com``, ``apple.com``, ``password``. The endpoint stays
    provider-agnostic: any provider Firebase has minted a token for is
    accepted.
    """

    uid: str
    email: str | None = None
    name: str | None = None
    provider_id: str | None = None


class UserEntity(BaseModel):
    id: str
    name: str
    lastName: str
    dni: str
    email: str
    phone: str
    avatarUrl: str | None = None
    # Soft-delete flag. `False` means the user requested account deletion —
    # the Firebase Auth identity is removed but the Firestore document is
    # kept for audit/traceability. Login must reject inactive users.
    isActive: bool = True
    deactivatedAt: int | None = None

class IAuthRepository(Protocol):
    async def create_user(self, email: str, password: str) -> str:
        """Create Firebase auth user and return the Firebase UID"""
        pass

    async def verify_password(self, email: str, password: str) -> tuple[str, str]:
        """Verify user credentials and return (Firebase UID, JWT ID Token)"""
        pass

    async def verify_id_token(self, id_token: str) -> str:
        """Verify a Firebase ID Token and return the Firebase UID"""
        pass

    async def resolve_identity(self, id_token: str) -> "FirebaseIdentity":
        """Verify a Firebase ID Token and return the full identity payload
        (uid + email + display name + provider). Used by the federated
        sign-in endpoint to upsert a Firestore profile when the caller
        signed in via Google / Apple / etc. for the first time."""
        pass

    async def revoke_refresh_tokens(self, uid: str) -> None:
        """Revoke all refresh tokens for the given Firebase UID"""
        pass

    async def delete_user(self, uid: str) -> None:
        """Permanently delete the Firebase Auth identity for the given UID."""
        pass

    async def send_password_reset_email(self, email: str) -> bool:
        """Triggers a password-reset email for the given address.

        Implementations should be idempotent and never reveal whether the
        email is registered (the email-enumeration mitigation lives at
        this boundary so callers can trust a uniform response). Returns
        ``True`` when the upstream provider accepted the request,
        ``False`` when the email was unknown — callers convert both into
        a single 200 response on the API.
        """
        pass

class IStorageRepository(Protocol):
    async def upload_profile_photo(self, user_id: str, file_content: bytes, content_type: str) -> str:
        """Upload profile photo to cloud storage and return the public URL"""
        pass

    async def delete_profile_photo(self, user_id: str) -> bool:
        """Delete every profile-photo blob owned by the user from cloud
        storage. Returns ``True`` when at least one blob was removed,
        ``False`` when none existed (the call is idempotent — re-running
        it after a successful delete is a safe no-op). Implementations
        should be best-effort: a network or permission error against a
        single extension should not abort the sweep of the others."""
        pass

class IUserRepository(Protocol):
    async def save_user(self, user: UserEntity) -> None:
        """Save user profile data to database"""
        pass

    async def get_user(self, user_id: str) -> UserEntity | None:
        """Retrieve user profile data by ID"""
        pass

    async def update_avatar_url(self, user_id: str, photo_url: str | None) -> None:
        """Update the avatarUrl field on the user document. Pass ``None``
        to clear the field — the delete-profile-photo flow leans on this
        to reset the value after wiping the underlying blob."""
        pass

    async def update_profile(self, user_id: str, fields: dict) -> None:
        """Patch a subset of fields on the user document."""
        pass

    async def set_active(self, user_id: str, is_active: bool, deactivated_at: int | None = None) -> None:
        """Flip the soft-delete flag (and stamp `deactivatedAt` when archiving)."""
        pass
