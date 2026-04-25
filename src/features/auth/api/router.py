from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from src.features.auth.application.services import AuthService
from src.features.auth.api.schemas import RegistrationRequest, LoginRequest, RegisteredUser, AuthToken, LogoutResponse
from src.features.auth.infrastructure.firebase_auth_adapter import FirebaseAuthAdapter
from src.features.auth.infrastructure.firestore_user_adapter import FirestoreUserAdapter
from email_validator import EmailNotValidError
from src.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

def get_auth_service(request: Request) -> AuthService:
    auth_repo = FirebaseAuthAdapter()
    user_repo = FirestoreUserAdapter(client=request.app.state.firestore_client)
    return AuthService(auth_repo, user_repo)

@router.post("/register")
async def register(request: RegistrationRequest, service: AuthService = Depends(get_auth_service)):
    try:
        logger.info(f"Incoming registration request for email: {request.email}")
        auth_token, user = await service.register(request)
        logger.info(f"Successfully registered user {user.id}")
        return {
            "token": auth_token,
            "user": user
        }
    except HTTPException as handled_exc:
        logger.warning(f"Registration aborted due to HTTPException: {handled_exc.detail}")
        raise handled_exc
    except ValueError as ve:
        logger.warning(f"Registration aborted due to ValueError (Validation/Input): {str(ve)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Internal Error during registration: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal sequence failed during registration.")

@router.post("/login")
async def login(request: LoginRequest, service: AuthService = Depends(get_auth_service)):
    try:
        logger.info(f"Incoming login request for email: {request.email}")
        auth_token, user = await service.login(request)
        logger.info(f"Successfully logged in user {user.id}")
        return {
            "token": auth_token,
            "user": user
        }
    except HTTPException as handled_exc:
        logger.warning(f"Login aborted due to HTTPException: {handled_exc.detail}")
        raise handled_exc
    except Exception as e:
        logger.error(f"Internal Error during login: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal sequence failed during login.")

@router.post("/logout", response_model=LogoutResponse)
async def logout(
    authorization: str | None = Header(default=None),
    service: AuthService = Depends(get_auth_service),
):
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Logout aborted: missing or malformed Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token in Authorization header.",
        )

    id_token = authorization.split(" ", 1)[1].strip()
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty Bearer token.",
        )

    try:
        logger.info("Incoming logout request")
        result = await service.logout(id_token)
        logger.info(f"Successfully logged out user {result.userId}")
        return result
    except HTTPException as handled_exc:
        logger.warning(f"Logout aborted due to HTTPException: {handled_exc.detail}")
        raise handled_exc
    except Exception as e:
        logger.error(f"Internal Error during logout: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal sequence failed during logout.",
        )
