from pydantic import BaseModel
from typing import Protocol

class UserEntity(BaseModel):
    id: str
    name: str
    lastName: str
    dni: str
    email: str
    phone: str
    avatarUrl: str | None = None

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

    async def revoke_refresh_tokens(self, uid: str) -> None:
        """Revoke all refresh tokens for the given Firebase UID"""
        pass

class IStorageRepository(Protocol):
    async def upload_profile_photo(self, user_id: str, file_content: bytes, content_type: str) -> str:
        """Upload profile photo to cloud storage and return the public URL"""
        pass

class IUserRepository(Protocol):
    async def save_user(self, user: UserEntity) -> None:
        """Save user profile data to database"""
        pass

    async def get_user(self, user_id: str) -> UserEntity | None:
        """Retrieve user profile data by ID"""
        pass

    async def update_avatar_url(self, user_id: str, photo_url: str) -> None:
        """Update only the avatarUrl field in the user document"""
        pass
