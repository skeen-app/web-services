import os
import httpx
from firebase_admin import auth
from fastapi import HTTPException

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
            # Mask detailed Firebase errors in production, but log them
            raise HTTPException(status_code=400, detail=str(e))

    async def verify_password(self, email: str, password: str) -> tuple[str, str]:
        if not self.web_api_key:
            raise HTTPException(status_code=500, detail="Firebase Web API Key not configured")

        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.web_api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            data = response.json()

            if response.status_code != 200:
                error_message = data.get("error", {}).get("message", "Authentication Failed")
                raise HTTPException(status_code=401, detail=f"Invalid credentials: {error_message}")

            uid = data["localId"]
            id_token = data["idToken"]
            return uid, id_token
