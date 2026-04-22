from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.core.middlewares.jwt import jwt_middleware

app = FastAPI(
    title="Skeen Backend",
    description="Skeen backend orchestrator for dermatological triage data in Peru.",
    version="1.0.0"
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

# Register routers here (to be added)
# e.g., app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)
