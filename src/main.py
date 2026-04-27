from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.core.middlewares.jwt import jwt_middleware
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

# Add custom JWT middleware
app.middleware("http")(jwt_middleware)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "skeen-backend"}

# Register routers
from src.features.auth.api.router import router as auth_router
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)
