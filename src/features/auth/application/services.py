import time
from fastapi import HTTPException
from src.features.auth.domain.entities import IAuthRepository, IUserRepository, UserEntity
from src.features.auth.api.schemas import RegistrationRequest, LoginRequest, RegisteredUser, AuthToken
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

        # Map to Output DTOs
        registered_user = RegisteredUser(
            id=user.id,
            name=user.name,
            lastName=user.lastName,
            dni=user.dni,
            email=user.email,
            phone=user.phone
        )
        auth_token = AuthToken(
            value=id_token,
            issuedAt=int(time.time())
        )
        
        logger.info(f"AuthService: Login sequence successful for UID: {uid}")
        return auth_token, registered_user
