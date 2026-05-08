import time
from fastapi import HTTPException
from src.features.auth.domain.entities import IAuthRepository, IUserRepository, UserEntity
from src.features.auth.api.schemas import (
    RegistrationRequest,
    LoginRequest,
    RegisteredUser,
    AuthToken,
    LogoutResponse,
    UpdateProfileRequest,
    DeleteAccountResponse,
    FederatedSignInResponse,
    CompleteProfileRequest,
)
from src.core.logger import get_logger

logger = get_logger(__name__)


def _split_name(full_name: str) -> tuple[str, str]:
    """Best-effort split of a "given family" string into (name, lastName).
    Federated providers like Google return a single ``name`` claim;
    Firestore stores the two halves separately."""
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))


class AuthService:
    def __init__(self, auth_repo: IAuthRepository, user_repo: IUserRepository):
        self.auth_repo = auth_repo
        self.user_repo = user_repo

    async def register(self, request: RegistrationRequest) -> tuple[AuthToken, RegisteredUser]:
        logger.info(f"AuthService: Initiating registration sequence for {request.email}")

        # Create Firebase Identity
        uid = await self.auth_repo.create_user(request.email, request.password)
        logger.info(f"AuthService: Firebase Identity created with UID: {uid}")

        # Build Domain Entity
        new_user = UserEntity(
            id=uid,
            name=request.name,
            lastName=request.lastName,
            dni=request.dni,
            email=request.email,
            phone=request.phone
        )

        # Save to Database
        await self.user_repo.save_user(new_user)
        logger.info(f"AuthService: User profile saved to database for UID: {uid}")

        # Exchange credentials for an idToken so the client is signed in after register
        _, id_token = await self.auth_repo.verify_password(request.email, request.password)

        registered_user = RegisteredUser(
            id=uid,
            name=new_user.name,
            lastName=new_user.lastName,
            dni=new_user.dni,
            email=new_user.email,
            phone=new_user.phone
        )
        auth_token = AuthToken(
            value=id_token,
            issuedAt=int(time.time())
        )
        return auth_token, registered_user

    async def login(self, request: LoginRequest) -> tuple[AuthToken, RegisteredUser]:
        logger.info(f"AuthService: Initiating login sequence for {request.email}")
        
        # Perform Identity verification
        uid, id_token = await self.auth_repo.verify_password(request.email, request.password)
        
        # Fetch profile
        user = await self.user_repo.get_user(uid)
        if not user:
            logger.warning(f"AuthService: User logged in via Firebase Identity but profile missing in Firestore (UID: {uid})")
            raise HTTPException(status_code=404, detail="User profile not found")

        # Block deactivated accounts. The Firebase Auth identity should
        # already be gone after a `DELETE /auth/me`, but we double-check
        # here to handle any window of eventual consistency.
        if not user.isActive:
            logger.warning(f"AuthService: Login rejected — account deactivated (UID: {uid})")
            raise HTTPException(status_code=403, detail="Account has been deactivated.")

        # Map to Output DTOs
        registered_user = RegisteredUser(
            id=user.id,
            name=user.name,
            lastName=user.lastName,
            dni=user.dni,
            email=user.email,
            phone=user.phone,
            avatarUrl=user.avatarUrl,
            isActive=user.isActive,
        )
        auth_token = AuthToken(
            value=id_token,
            issuedAt=int(time.time())
        )
        
        logger.info(f"AuthService: Login sequence successful for UID: {uid}")
        return auth_token, registered_user

    async def update_profile(self, id_token: str, request: UpdateProfileRequest) -> RegisteredUser:
        """Patch mutable profile fields (name, lastName, phone) for the
        authenticated user. DNI and email are not editable: DNI is the
        government identifier and email is the Firebase Auth login.
        """
        logger.info("AuthService: Initiating profile update sequence")
        uid = await self.auth_repo.verify_id_token(id_token)

        user = await self.user_repo.get_user(uid)
        if not user:
            raise HTTPException(status_code=404, detail="User profile not found")
        if not user.isActive:
            raise HTTPException(status_code=403, detail="Account has been deactivated.")

        # Only persist fields that were actually provided. `model_dump`
        # with `exclude_unset=True` drops unset attributes — so PATCH
        # semantics are preserved (omit a field to leave it unchanged).
        delta = request.model_dump(exclude_unset=True, exclude_none=True)
        if delta:
            await self.user_repo.update_profile(uid, delta)

        merged = user.model_copy(update=delta)
        logger.info(f"AuthService: Profile update successful for UID: {uid} ({list(delta.keys())})")
        return RegisteredUser(
            id=merged.id,
            name=merged.name,
            lastName=merged.lastName,
            dni=merged.dni,
            email=merged.email,
            phone=merged.phone,
            avatarUrl=merged.avatarUrl,
            isActive=merged.isActive,
        )

    async def delete_account(self, id_token: str) -> DeleteAccountResponse:
        """Soft-deletes the Firestore profile (`isActive=False` +
        `deactivatedAt`) and hard-deletes the Firebase Auth identity so the
        credentials can no longer authenticate. The audit record stays.
        """
        logger.info("AuthService: Initiating account deletion sequence")
        uid = await self.auth_repo.verify_id_token(id_token)

        deactivated_at = int(time.time())

        # 1) Mark Firestore as inactive first — if step 2 fails, the user
        #    is already locked out at the application layer.
        await self.user_repo.set_active(uid, is_active=False, deactivated_at=deactivated_at)

        # 2) Revoke any active refresh tokens so existing sessions die now.
        try:
            await self.auth_repo.revoke_refresh_tokens(uid)
        except HTTPException as e:
            logger.warning(f"AuthService: revoke_refresh_tokens failed during deletion (UID: {uid}) — proceeding. {e.detail}")

        # 3) Hard-delete the Firebase Auth identity.
        await self.auth_repo.delete_user(uid)

        logger.info(f"AuthService: Account deletion complete for UID: {uid}")
        return DeleteAccountResponse(
            deleted=True,
            userId=uid,
            deactivatedAt=deactivated_at,
        )

    async def sign_in_with_firebase_token(
        self, id_token: str
    ) -> FederatedSignInResponse:
        """Provider-agnostic federated sign-in.

        Verifies the Firebase ID token, looks up the Firestore profile
        by UID, and either:
          - Returns the existing profile + a fresh AuthToken made of the
            same id_token (caller will use it as bearer), or
          - Creates a partial profile with email + display name from the
            Firebase Auth user record and flips ``isNewUser=true`` so
            the mobile client can route to the complete-profile screen.

        Account linking is handled upstream by Firebase: when "multiple
        accounts per email" is disabled in the project settings, signing
        in with Google for an email already registered with
        password-auth lands on the same UID — so the lookup here just
        returns the existing profile.
        """
        identity = await self.auth_repo.resolve_identity(id_token)
        logger.info(
            f"AuthService: federated sign-in for uid={identity.uid} "
            f"provider={identity.provider_id}"
        )

        existing = await self.user_repo.get_user(identity.uid)
        if existing and existing.isActive:
            registered_user = RegisteredUser(
                id=existing.id,
                name=existing.name,
                lastName=existing.lastName,
                dni=existing.dni,
                email=existing.email,
                phone=existing.phone,
                avatarUrl=existing.avatarUrl,
                isActive=existing.isActive,
            )
            return FederatedSignInResponse(
                token=AuthToken(value=id_token, issuedAt=int(time.time())),
                user=registered_user,
                isNewUser=False,
            )
        if existing and not existing.isActive:
            raise HTTPException(
                status_code=403, detail="Account has been deactivated."
            )

        # Brand-new federated identity — create a partial profile. DNI
        # and phone start empty; the mobile flow takes the user through
        # CompleteProfileScreen before letting them into /home.
        first_name, last_name = _split_name(identity.name or "")
        new_user = UserEntity(
            id=identity.uid,
            name=first_name,
            lastName=last_name,
            dni="",
            email=identity.email or "",
            phone="",
        )
        await self.user_repo.save_user(new_user)
        registered_user = RegisteredUser(
            id=new_user.id,
            name=new_user.name,
            lastName=new_user.lastName,
            dni=new_user.dni,
            email=new_user.email,
            phone=new_user.phone,
            avatarUrl=new_user.avatarUrl,
            isActive=new_user.isActive,
        )
        logger.info(
            f"AuthService: provisioned federated profile for uid={identity.uid}"
        )
        return FederatedSignInResponse(
            token=AuthToken(value=id_token, issuedAt=int(time.time())),
            user=registered_user,
            isNewUser=True,
        )

    async def complete_profile(
        self, id_token: str, request: CompleteProfileRequest
    ) -> RegisteredUser:
        """Fills DNI + phone (and optionally name/lastName) on a partial
        profile created by federated sign-in. Once DNI is set the
        endpoint refuses to overwrite it — the regular update flow
        (``PATCH /auth/me``) then takes over for everything except DNI."""
        uid = await self.auth_repo.verify_id_token(id_token)
        user = await self.user_repo.get_user(uid)
        if not user:
            raise HTTPException(status_code=404, detail="User profile not found")
        if not user.isActive:
            raise HTTPException(
                status_code=403, detail="Account has been deactivated."
            )
        if user.dni and user.dni.strip():
            raise HTTPException(
                status_code=409,
                detail="Profile already completed.",
            )

        delta: dict = {
            "dni": request.dni,
            "phone": request.phone,
        }
        if request.name and request.name.strip():
            delta["name"] = request.name.strip()
        if request.lastName and request.lastName.strip():
            delta["lastName"] = request.lastName.strip()

        await self.user_repo.update_profile(uid, delta)
        merged = user.model_copy(update=delta)
        return RegisteredUser(
            id=merged.id,
            name=merged.name,
            lastName=merged.lastName,
            dni=merged.dni,
            email=merged.email,
            phone=merged.phone,
            avatarUrl=merged.avatarUrl,
            isActive=merged.isActive,
        )

    async def logout(self, id_token: str) -> LogoutResponse:
        logger.info("AuthService: Initiating logout sequence")

        # Verify token authenticity and extract UID
        uid = await self.auth_repo.verify_id_token(id_token)

        # Revoke all refresh tokens for this user in Firebase
        await self.auth_repo.revoke_refresh_tokens(uid)
        logger.info(f"AuthService: Refresh tokens revoked for UID: {uid}")

        return LogoutResponse(
            loggedOut=True,
            userId=uid,
            loggedOutAt=int(time.time())
        )
