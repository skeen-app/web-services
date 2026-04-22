---
description: Initializes the FastAPI boilerplate, Dockerfile, and the 4 bounded context directories.
---
# skeen-init-backend

## Goal
Quick start without re-explaining the DDD structure.

## Steps
1. Create `src/core/` for shared security, config, and middlewares.
2. Create bounded contexts in `src/features/`: `auth`, `patient`, `detection`, `system`.
3. Within each feature context, create `domain/`, `application/`, `infrastructure/`, and `api/` (or routers).
4. Generate a Python 3.11 FastAPI Dockerfile optimized for Cloud Run.
5. Set up `src/main.py` entry point with a health check and JWT middleware base.
