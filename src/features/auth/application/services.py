import time
from fastapi import HTTPException
from src.features.auth.domain.entities import IAuthRepository, IUserRepository, UserEntity
from src.features.auth.api.schemas import RegistrationRequest, LoginRequest, RegisteredUser, AuthToken

class AuthService:
    def __init__(self, auth_repo: IAuthRepository, user_repo: IUserRepository):
        self.auth_repo = auth_repo
        self.user_repo = user_repo

    async def register(self, request: RegistrationRequest) -> RegisteredUser:
        # Check if user with email already exists in Firestore/Auth can be handled gracefully
        # Create Firebase Identity
        uid = await self.auth_repo.create_user(request.email, request.password)
        
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

        # Convert to Output DTO
        return RegisteredUser(
            id=uid,
            name=new_user.name,
            lastName=new_user.lastName,
            dni=new_user.dni,
            email=new_user.email,
            phone=new_user.phone
        )

    async def login(self, request: LoginRequest) -> tuple[AuthToken, RegisteredUser]:
        # Perform Identity verification
        uid, id_token = await self.auth_repo.verify_password(request.email, request.password)

        # Fetch profile
        user = await self.user_repo.get_user(uid)
        if not user:
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

        return auth_token, registered_user
