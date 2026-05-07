from pydantic import BaseModel, EmailStr, Field, field_validator
import re

class RegistrationRequest(BaseModel):
    name: str = Field(..., min_length=1)
    lastName: str = Field(..., min_length=1)
    dni: str = Field(..., description="DNI exactly 8 digits")
    email: EmailStr
    phone: str
    password: str

    @field_validator('dni')
    @classmethod
    def validate_dni(cls, v: str) -> str:
        if not re.fullmatch(r'\d{8}', v):
            raise ValueError("DNI must be exactly 8 digits")
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character")
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisteredUser(BaseModel):
    id: str
    name: str
    lastName: str
    dni: str
    email: EmailStr
    phone: str
    avatarUrl: str | None = None
    isActive: bool = True


class UpdateProfileRequest(BaseModel):
    """PATCH /auth/me — every field optional; only provided fields are
    updated. DNI and email are intentionally excluded: they are identity
    anchors (gov ID and Firebase Auth login)."""
    name: str | None = Field(default=None, min_length=1)
    lastName: str | None = Field(default=None, min_length=1)
    phone: str | None = Field(default=None, min_length=1)


class DeleteAccountResponse(BaseModel):
    deleted: bool
    userId: str
    deactivatedAt: int
    message: str = "Account deactivated and identity removed"

class AuthToken(BaseModel):
    value: str
    issuedAt: int

class LogoutResponse(BaseModel):
    loggedOut: bool
    userId: str
    loggedOutAt: int
    message: str = "Session revoked successfully"

class ProfilePhotoResponse(BaseModel):
    url: str
    uploadedAt: int


class PasswordResetRequest(BaseModel):
    """Payload for ``POST /auth/password-reset/request`` (public).

    A single field — we never accept the new password here; Firebase's
    hosted action page is the only surface that takes the new credential,
    one-time-token-bound.
    """

    email: EmailStr


class PasswordResetResponse(BaseModel):
    """Generic response intentionally indistinguishable between
    "email registered → email sent" and "email unknown → no-op". The
    email-enumeration mitigation lives at this contract.
    """

    sent: bool = True
    message: str = (
        "If that email is registered with skeen, password reset "
        "instructions have been sent."
    )


class MePasswordResetResponse(BaseModel):
    """Response for ``POST /auth/me/password-reset`` (authenticated).

    The caller is already authenticated, so we can safely confirm the
    target email — partially masked for shoulder-surfing protection
    when the screen is shown in public.
    """

    sent: bool = True
    email: str = Field(
        ...,
        description="Email address with the local-part partially masked, e.g. 'jo***@gmail.com'.",
    )
    message: str = "Password reset instructions have been sent to your inbox."


# Re-export so router.py imports stay tidy.
__all__ = [
    "RegistrationRequest",
    "LoginRequest",
    "RegisteredUser",
    "AuthToken",
    "LogoutResponse",
    "ProfilePhotoResponse",
    "UpdateProfileRequest",
    "DeleteAccountResponse",
    "PasswordResetRequest",
    "PasswordResetResponse",
    "MePasswordResetResponse",
]
