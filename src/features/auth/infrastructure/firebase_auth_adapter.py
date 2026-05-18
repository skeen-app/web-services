import os
import httpx
from firebase_admin import auth
from fastapi import HTTPException
from src.core.logger import get_logger
from src.features.auth.domain.entities import FirebaseIdentity

logger = get_logger(__name__)

class FirebaseAuthAdapter:
    def __init__(self):
        # FIREBASE_WEB_API_KEY must be set in the environment or GCP Secret Manager
        self.web_api_key = (os.getenv("FIREBASE_WEB_API_KEY") or "").strip()

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

    async def resolve_identity(self, id_token: str) -> FirebaseIdentity:
        """Same revocation / expiry guarantees as :meth:`verify_id_token`,
        but returns the full identity payload extracted from the decoded
        claims. Used by the federated sign-in endpoint."""
        try:
            decoded = auth.verify_id_token(id_token, check_revoked=True)
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

        return FirebaseIdentity(
            uid=decoded["uid"],
            email=decoded.get("email"),
            name=decoded.get("name"),
            provider_id=(decoded.get("firebase") or {}).get("sign_in_provider"),
        )

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

    async def send_password_reset_email(self, email: str) -> bool:
        """Asks Firebase Identity Toolkit to email a reset link.

        Uses ``accounts:sendOobCode`` (mode ``PASSWORD_RESET``) so the email
        delivery + template are handled by Firebase — no SMTP / SendGrid
        dependency on our side. The template is configured in the Firebase
        Console (Authentication → Templates → Password reset).

        Returns:
            ``True``  — Firebase accepted the request and queued the email.
            ``False`` — email is unknown to Firebase. Caller MUST still
                        respond 200 to the user (email-enumeration
                        mitigation lives in the application service).
        """
        if not self.web_api_key:
            logger.error(
                "FirebaseAuthAdapter: FIREBASE_WEB_API_KEY is not configured."
            )
            raise HTTPException(
                status_code=500, detail="Internal configuration error."
            )

        url = (
            "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode"
            f"?key={self.web_api_key}"
        )
        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
        except httpx.RequestError as exc:
            logger.error(
                f"FirebaseAuthAdapter: HTTP error contacting Identity Toolkit: {exc}"
            )
            raise HTTPException(
                status_code=503, detail="Identity service is unavailable."
            )

        if response.status_code == 200:
            logger.info("FirebaseAuthAdapter: password reset email queued.")
            return True

        # Identity Toolkit returns 400 with an error body when the email
        # isn't registered or when rate-limited per email. We treat the
        # "EMAIL_NOT_FOUND" case as a no-op success at the API layer to
        # prevent enumeration; everything else is logged and re-raised as
        # 503 so the caller knows something genuinely failed upstream.
        try:
            data = response.json()
            error_message = (data.get("error", {}) or {}).get("message", "")
        except Exception:
            error_message = ""

        if response.status_code == 400 and error_message == "EMAIL_NOT_FOUND":
            logger.info(
                "FirebaseAuthAdapter: password reset requested for unknown email."
            )
            return False

        if response.status_code == 400 and "TOO_MANY_ATTEMPTS_TRY_LATER" in error_message:
            # Firebase enforces its own per-email rate limit — surface as
            # 429 so the client can show a "try again later" message.
            logger.warning(
                "FirebaseAuthAdapter: Identity Toolkit rate-limited the reset request."
            )
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please try again later.",
            )

        logger.error(
            f"FirebaseAuthAdapter: sendOobCode returned {response.status_code}: "
            f"{error_message or response.text}"
        )
        raise HTTPException(
            status_code=503, detail="Could not send password reset email."
        )
