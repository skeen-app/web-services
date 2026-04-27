import os
import httpx
from firebase_admin import auth
from fastapi import HTTPException
from src.core.logger import get_logger

logger = get_logger(__name__)

class FirebaseAuthAdapter:
    def __init__(self):
        # FIREBASE_WEB_API_KEY must be set in the environment or GCP Secret Manager
        self.web_api_key = os.getenv("FIREBASE_WEB_API_KEY")

    async def create_user(self, email: str, password: str) -> str:
        try:
            user_record = auth.create_user(
                email=email,
                password=password
            )
            return user_record.uid
        except Exception as e:
            logger.error(f"FirebaseAuthAdapter: Failed to create user. Reason: {e}")
            # Mask detailed Firebase errors in production, but log them
            raise HTTPException(status_code=400, detail=str(e))

    async def verify_password(self, email: str, password: str) -> tuple[str, str]:
        if not self.web_api_key:
            logger.error("FirebaseAuthAdapter: FIREBASE_WEB_API_KEY is not configured.")
            raise HTTPException(status_code=500, detail="Internal configuration error.")

        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.web_api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                data = response.json()

                if response.status_code != 200:
                    error_message = data.get("error", {}).get("message", "Authentication Failed")
                    logger.warning(f"FirebaseAuthAdapter: Login rejected by Identity Toolkit. Error: {error_message}")
                    raise HTTPException(status_code=401, detail=f"Invalid credentials: {error_message}")

                return data["localId"], data["idToken"]
        except httpx.RequestError as exc:
            logger.error(f"FirebaseAuthAdapter: HTTP Request failed connecting to Google API: {exc}")
            raise HTTPException(status_code=500, detail="External identity service is unavailable.")

    async def verify_id_token(self, id_token: str) -> str:
        try:
            decoded = auth.verify_id_token(id_token, check_revoked=True)
            return decoded["uid"]
        except auth.RevokedIdTokenError:
            logger.warning("FirebaseAuthAdapter: ID token has been revoked.")
            raise HTTPException(status_code=401, detail="Session already revoked.")
        except auth.ExpiredIdTokenError:
            logger.warning("FirebaseAuthAdapter: ID token expired.")
            raise HTTPException(status_code=401, detail="Session expired.")
        except auth.InvalidIdTokenError as e:
            logger.warning(f"FirebaseAuthAdapter: Invalid ID token. Reason: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
        except Exception as e:
            logger.error(f"FirebaseAuthAdapter: Unexpected error verifying ID token: {e}")
            raise HTTPException(status_code=401, detail="Could not verify authentication token.")

    async def revoke_refresh_tokens(self, uid: str) -> None:
        try:
            auth.revoke_refresh_tokens(uid)
        except Exception as e:
            logger.error(f"FirebaseAuthAdapter: Failed to revoke refresh tokens for UID {uid}. Reason: {e}")
            raise HTTPException(status_code=500, detail="Failed to revoke session.")

    async def delete_user(self, uid: str) -> None:
        # Hard-removes the identity from Firebase Auth so the credentials can
        # no longer be used. The Firestore profile is kept (soft-deleted via
        # `isActive=False`) for audit/traceability.
        try:
            auth.delete_user(uid)
        except auth.UserNotFoundError:
            # Already gone — treat as success so retries are idempotent.
            logger.info(f"FirebaseAuthAdapter: delete_user no-op (UID {uid} not found).")
        except Exception as e:
            logger.error(f"FirebaseAuthAdapter: Failed to delete user {uid}. Reason: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete identity.")
