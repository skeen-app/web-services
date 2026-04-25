import time
from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, status
from src.features.auth.application.services import AuthService
from src.features.auth.application.profile_photo_service import ProfilePhotoService
from src.features.auth.api.schemas import (
    RegistrationRequest, LoginRequest, RegisteredUser,
    AuthToken, LogoutResponse, ProfilePhotoResponse,
)
from src.features.auth.infrastructure.firebase_auth_adapter import FirebaseAuthAdapter
from src.features.auth.infrastructure.firestore_user_adapter import FirestoreUserAdapter
from src.features.auth.infrastructure.cloud_storage_adapter import CloudStorageAdapter
from src.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

def get_auth_service(request: Request) -> AuthService:
    auth_repo = FirebaseAuthAdapter()
    user_repo = FirestoreUserAdapter(client=request.app.state.firestore_client)
    return AuthService(auth_repo, user_repo)

def get_profile_photo_service(request: Request) -> ProfilePhotoService:
    storage_repo = CloudStorageAdapter(client=request.app.state.storage_client)
    user_repo = FirestoreUserAdapter(client=request.app.state.firestore_client)
    return ProfilePhotoService(storage_repo, user_repo)

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

@router.post("/profile-photo", response_model=ProfilePhotoResponse)
async def upload_profile_photo(
    file: UploadFile,
    request: Request,
    authorization: str = Header(..., description="Bearer <Firebase ID Token>"),
    service: ProfilePhotoService = Depends(get_profile_photo_service),
):
    # --- Authenticate via Firebase JWT ---
    if not authorization.startswith("Bearer "):
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
        auth_adapter = FirebaseAuthAdapter()
        uid = await auth_adapter.verify_id_token(id_token)
        logger.info(f"Profile photo upload requested by user {uid}")

        # Read file bytes
        file_content = await file.read()
        content_type = file.content_type or "application/octet-stream"
        filename = file.filename or "unknown"

        # Delegate to application service
        public_url = await service.upload_profile_photo(
            user_id=uid,
            file_content=file_content,
            filename=filename,
            content_type=content_type,
        )

        logger.info(f"Profile photo uploaded successfully for user {uid}")
        return ProfilePhotoResponse(url=public_url, uploadedAt=int(time.time()))

    except HTTPException as handled_exc:
        logger.warning(f"Profile photo upload aborted: {handled_exc.detail}")
        raise handled_exc
    except Exception as e:
        logger.error(f"Internal error during profile photo upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal sequence failed during profile photo upload.",
        )
