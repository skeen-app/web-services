from src.features.auth.application.identity_service import IdentityService
from src.features.detection.domain.entities import (
    IIdentityValidator,
    RequesterIdentity,
)


class AuthIdentityACL(IIdentityValidator):
    """Anti-Corruption Layer between Detection and the Auth bounded context.

    Detection speaks ``RequesterIdentity``; Auth speaks
    ``AuthenticatedIdentity``. This adapter is the *only* class in
    Detection allowed to import from ``features.auth`` — it pins the
    translation to a single boundary so the rest of Detection stays
    decoupled from Firebase / Auth-specific concepts.
    """

    def __init__(self, identity_service: IdentityService):
        self._identity_service = identity_service

    async def resolve_from_authorization(
        self, authorization_header: str | None
    ) -> RequesterIdentity:
        identity = await self._identity_service.authenticate_bearer(
            authorization_header
        )
        return RequesterIdentity(uid=identity.uid)
