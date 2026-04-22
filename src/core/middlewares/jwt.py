from fastapi import Request
from fastapi.responses import JSONResponse
import jwt
import os

# Note: In a real environment, load public keys from Firebase or a verifiable source.
SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-key")

async def jwt_middleware(request: Request, call_next):
    # Exclude /health from authentication
    if request.url.path in ["/health", "/docs", "/openapi.json"]:
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        pass
        # Depending on requirements, we can block here or let specific routers handle auth.
        # For a global middleware, you might block it:
        # return JSONResponse(status_code=401, content={"detail": "Missing Authorization Header"})
    else:
        token = auth_header.split(" ")[1]
        try:
            # Here you would typically verify against Firebase Auth
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], options={"verify_signature": False})
            request.state.user = payload
        except jwt.PyJWTError:
            pass
            # return JSONResponse(status_code=401, content={"detail": "Invalid Token"})
            
    response = await call_next(request)
    return response
