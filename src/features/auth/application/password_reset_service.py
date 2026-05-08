from fastapi import HTTPException

from src.core.logger import get_logger
from src.features.auth.api.schemas import (
    MePasswordResetResponse,
    PasswordResetResponse,
)
from src.features.auth.application.identity_service import IdentityService
from src.features.auth.domain.entities import IAuthRepository, IUserRepository

logger = get_logger(__name__)


class PasswordResetService:
    """Use-case service that orchestrates the password-reset email flow.

    Two entry points:
      • ``request_for_email`` — public flow, never reveals whether the
        address is registered (email-enumeration mitigation).
      • ``request_for_authenticated`` — authenticated flow used by the
        in-app "Privacy & Security → Change password" surface; resolves
        the target email from the user's Firestore profile so the client
        doesn't have to re-type it.
    """

    def __init__(
        self,
        auth_repo: IAuthRepository,
        user_repo: IUserRepository,
        identity_service: IdentityService,
    ):
        self._auth_repo = auth_repo
        self._user_repo = user_repo
        self._identity_service = identity_service

    async def request_for_email(self, email: str) -> PasswordResetResponse:
        # The adapter raises 429 on Firebase rate-limit and 503 on transport
        # errors; everything else (including unknown email) collapses into a
        # successful response so attackers can't enumerate accounts.
        await self._auth_repo.send_password_reset_email(email)
        logger.info("PasswordResetService: public reset request processed.")
        return PasswordResetResponse()

    async def request_for_authenticated(
        self, authorization_header: str | None
    ) -> MePasswordResetResponse:
        identity = await self._identity_service.authenticate_bearer(
            authorization_header
        )
        user = await self._user_repo.get_user(identity.uid)
        if not user:
            logger.warning(
                f"PasswordResetService: profile missing for uid {identity.uid}"
            )
            raise HTTPException(status_code=404, detail="User profile not found")
        if not user.isActive:
            raise HTTPException(
                status_code=403, detail="Account has been deactivated."
            )

        sent = await self._auth_repo.send_password_reset_email(user.email)
        if not sent:
            # Firebase doesn't know this email — that means the Firestore
            # profile and the Firebase Auth identity are out-of-sync, which
            # should never happen in a healthy system. Log loudly and 500.
            logger.error(
                f"PasswordResetService: Firebase says email unknown for uid "
                f"{identity.uid} — identity / profile drift!"
            )
            raise HTTPException(
                status_code=500, detail="Could not initiate password reset."
            )

        logger.info(
            f"PasswordResetService: authenticated reset email queued for "
            f"uid {identity.uid}"
        )
        return MePasswordResetResponse(email=_mask_email(user.email))


def _mask_email(email: str) -> str:
    """Masks the local-part of an email address, preserving the first two
    characters and the domain. Handy for partial-confirmation displays.

    Examples:
        ``john.doe@example.com`` → ``jo***@example.com``
        ``a@x.io``               → ``a***@x.io``
    """

    try:
        local, domain = email.split("@", 1)
    except ValueError:
        return email
    if len(local) <= 2:
        return f"{local}***@{domain}"
    return f"{local[:2]}***@{domain}"
