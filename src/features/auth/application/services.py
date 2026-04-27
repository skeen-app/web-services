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
)
from src.core.logger import get_logger

logger = get_logger(__name__)

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
