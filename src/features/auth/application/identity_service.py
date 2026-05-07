from dataclasses import dataclass

from fastapi import HTTPException, status

from src.core.logger import get_logger
from src.features.auth.domain.entities import IAuthRepository

logger = get_logger(__name__)


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """Published value object exposed by the Auth bounded context.

    Stable contract that other contexts may consume via an
    Anti-Corruption Layer. Adding fields here is a Published Language
    change and must remain backward-compatible.
    """

    uid: str


class IdentityService:
    """Open Host Service of the Auth bounded context.

    Encapsulates bearer-token parsing and Firebase ID-token verification
    so downstream contexts never depend on Firebase Admin SDK details.
    """

    def __init__(self, auth_repo: IAuthRepository):
        self._auth_repo = auth_repo

    async def authenticate_bearer(
        self,
        authorization_header: str | None,
    ) -> AuthenticatedIdentity:
        if not authorization_header or not authorization_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Bearer token in Authorization header.",
            )
        token = authorization_header.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Empty Bearer token.",
            )
        uid = await self._auth_repo.verify_id_token(token)
        return AuthenticatedIdentity(uid=uid)


def build_default_identity_service() -> IdentityService:
    """Factory used by other contexts' composition roots.

    Hides the concrete ``IAuthRepository`` implementation so consumers
    never import from ``features.auth.infrastructure``.
    """

    from src.features.auth.infrastructure.firebase_auth_adapter import (
        FirebaseAuthAdapter,
    )

    return IdentityService(FirebaseAuthAdapter())
