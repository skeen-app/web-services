from fastapi import APIRouter, Depends, HTTPException, status
from src.features.auth.application.services import AuthService
from src.features.auth.api.schemas import RegistrationRequest, LoginRequest, RegisteredUser, AuthToken
from src.features.auth.infrastructure.firebase_auth_adapter import FirebaseAuthAdapter
from src.features.auth.infrastructure.firestore_user_adapter import FirestoreUserAdapter
from email_validator import EmailNotValidError

router = APIRouter()

def get_auth_service() -> AuthService:
    # Basic Dependency Injection
    auth_repo = FirebaseAuthAdapter()
    user_repo = FirestoreUserAdapter()
    return AuthService(auth_repo, user_repo)

@router.post("/register", response_model=RegisteredUser)
async def register(request: RegistrationRequest, service: AuthService = Depends(get_auth_service)):
    try:
        return await service.register(request)
    except HTTPException as handled_exc:
        raise handled_exc
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        # In production log 'e' silently. Return a safe response.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal sequence failed during registration.")

@router.post("/login")
async def login(request: LoginRequest, service: AuthService = Depends(get_auth_service)):
    try:
        auth_token, user = await service.login(request)
        return {
            "token": auth_token,
            "user": user
        }
    except HTTPException as handled_exc:
        raise handled_exc
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal sequence failed during login.")
