from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from src.core.middlewares.jwt import jwt_middleware
from src.core.rate_limit import limiter
from google.cloud import firestore, storage
import firebase_admin
from dotenv import load_dotenv
import os
from src.core.logger import get_logger

logger = get_logger(__name__)

# Load Environment Variables from .env
load_dotenv()

# Initialize Firebase App
try:
    if not firebase_admin._apps:
        # If GOOGLE_APPLICATION_CREDENTIALS is set, firebase-admin uses it automatically
        firebase_admin.initialize_app()
        logger.info("Firebase Admin SDK implicitly initialized via GOOGLE_APPLICATION_CREDENTIALS.")
except Exception as e:
    logger.error(f"Error initializing Firebase: {str(e)}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_id = os.getenv("FIRESTORE_DATABASE_ID", "(default)")
    app.state.firestore_client = firestore.Client(database=db_id)
    app.state.storage_client = storage.Client()
    logger.info(f"Firestore client initialized for database: {db_id}")
    logger.info("Cloud Storage client initialized.")
    yield
    app.state.firestore_client.close()
    logger.info("Firestore client closed.")


app = FastAPI(
    title="Skeen Backend",
    description="Skeen backend orchestrator for dermatological triage data in Peru.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting — opted-in per-route via @limiter.limit decorators. We
# return a plain JSON 429 to keep the schema consistent with the rest of
# the error responses.
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


# Add custom JWT middleware
app.middleware("http")(jwt_middleware)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "skeen-backend"}

# Register routers
from src.features.auth.api.router import router as auth_router
from src.features.detection.api.router import router as detection_router
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(detection_router, prefix="/api/v1/scans", tags=["Scans"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)
