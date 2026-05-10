# 🩺 Skeen — Backend API

> Backend orchestrator for **Skeen**, an AI-powered dermatological triage mobile application built for the Peruvian market. The API handles user authentication, skin-scan lifecycle management, and curated medical article delivery.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Features & Endpoints](#features--endpoints)
- [Integrated Services](#integrated-services)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)

---

## Overview

Skeen is a mobile health (mHealth) platform that enables users to capture skin lesions through an AR-assisted camera, receive an AI-driven risk classification (low / medium / high), and access expert-curated dermatology articles — all without storing any Personally Identifiable Information (PII) in scan documents.

This repository contains the **backend REST API** that powers the entire data layer:

- **User identity** — registration, login (email + federated Google sign-in), password reset, profile photos, and soft-delete account management.
- **Scan pipeline** — client-generated scan creation, signed-URL image upload directly to Cloud Storage (the API never receives the blob), and scan history/stats retrieval.
- **Expert insights** — real-time PubMed article search filtered by dermatology categories, with an in-process TTL cache to reduce upstream load.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Framework** | FastAPI (Python 3.11+) |
| **Runtime** | Uvicorn (ASGI) |
| **Validation** | Pydantic v2 |
| **Auth** | Firebase Admin SDK (JWT verification) |
| **Database** | Google Cloud Firestore |
| **Object Storage** | Google Cloud Storage (signed URLs) |
| **Secrets** | Google Cloud Secret Manager |
| **Logging** | Google Cloud Logging + custom centralized logger |
| **Rate Limiting** | SlowAPI (per-IP, opt-in per route) |
| **HTTP Client** | httpx (async, for PubMed E-utilities) |
| **Deployment** | Google Cloud Run (containerized) |

---

## Architecture

The backend follows a **Domain-Driven Design (DDD)** approach organized by **feature-first bounded contexts**:

```
┌──────────────────────────────────────────────────────┐
│                     FastAPI App                      │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │    Auth     │  │  Detection   │  │   Experts    │ │
│  │  Context    │  │   Context    │  │   Context    │ │
│  └─────┬──────┘  └──────┬───────┘  └──────┬───────┘ │
│        │                │                  │         │
│  ┌─────▼──────┐  ┌──────▼───────┐  ┌──────▼───────┐ │
│  │   api/     │  │    api/      │  │    api/      │ │
│  │ application│  │ application  │  │ application  │ │
│  │  domain/   │  │   domain/    │  │   domain/    │ │
│  │  infra/    │  │    infra/    │  │    infra/    │ │
│  └────────────┘  └──────────────┘  └──────────────┘ │
└──────────────────────┬───────────────────────────────┘
                       │
          ┌────────────┼────────────────┐
          ▼            ▼                ▼
   ┌────────────┐ ┌──────────┐  ┌────────────┐
   │  Firebase   │ │Firestore │  │Cloud Storage│
   │  Auth SDK   │ │          │  │(Signed URLs)│
   └────────────┘ └──────────┘  └────────────┘
```

Each bounded context contains four layers:

| Layer | Responsibility |
|---|---|
| `api/` | HTTP routers, Pydantic request/response schemas, dependency injection |
| `application/` | Use-case orchestration (services), business logic coordination |
| `domain/` | Entities, value objects, and repository interface protocols |
| `infrastructure/` | Concrete adapters (Firestore, Cloud Storage, Firebase Auth, PubMed) |

**Cross-context communication** uses an **Anti-Corruption Layer (ACL)** — e.g., the Detection context resolves caller identity via an ACL adapter that wraps Auth's `IdentityService`, keeping bounded contexts decoupled.

---

## Features & Endpoints

### 🔐 Auth — `/api/v1/auth`

| Method | Path | Description |
|---|---|---|
| `POST` | `/register` | Email/password registration → Firebase user + Firestore profile |
| `POST` | `/login` | Email/password login → Firebase JWT |
| `POST` | `/logout` | Revoke refresh tokens |
| `POST` | `/firebase` | Federated sign-in (Google / Apple) via Firebase ID token |
| `PATCH` | `/me` | Update profile fields (name, phone, etc.) |
| `POST` | `/me/complete-profile` | Complete partial profile after federated sign-in (DNI + phone) |
| `DELETE` | `/me` | Soft-delete account (Firebase Auth removed, Firestore kept for audit) |
| `POST` | `/me/password-reset` | Authenticated password-reset request (resolves email from profile) |
| `POST` | `/password-reset/request` | Public password-reset (rate-limited 5/hr, email-enum safe) |
| `POST` | `/profile-photo` | Upload profile photo → Cloud Storage, returns public URL |

### 📸 Scans — `/api/v1/scans`

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Register a new scan (client-generated UUID, AI metadata) |
| `POST` | `/{scan_id}/image` | Confirm image upload (client PUT to signed URL, API marks done) |
| `GET` | `/` | List all scans for the authenticated user |
| `GET` | `/stats` | Aggregated scan statistics for the user |
| `GET` | `/{scan_id}` | Get a single scan with a time-limited image download URL |
| `DELETE` | `/{scan_id}` | Delete scan document + Cloud Storage object |

### 📚 Experts — `/api/v1/experts`

| Method | Path | Description |
|---|---|---|
| `GET` | `/articles` | Curated dermatology articles from PubMed (filterable by category: prevention, detection, treatment) |

### ❤️ Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe for Cloud Run |

---

## Integrated Services

### Google Cloud Platform

- **Cloud Run** — Serverless container runtime. The Dockerfile builds a slim Python 3.11 image and runs Uvicorn with `--proxy-headers` for correct client IP forwarding behind the GCP load balancer.
- **Cloud Firestore** — NoSQL document database. User profiles stored in `users/{uid}`, scans as a subcollection `users/{uid}/scans/{scan_id}`. Supports configurable database ID via `FIRESTORE_DATABASE_ID`.
- **Cloud Storage** — Stores scan images and profile photos. Scan images use **signed URLs** for direct client upload (PUT) and time-limited download (GET), keeping blobs off the Cloud Run instance.
- **Cloud Secret Manager** — Securely stores sensitive configuration (API keys, credentials).

### Firebase

- **Firebase Admin SDK** — Server-side JWT verification for all authenticated endpoints. Supports both email/password and federated provider tokens (Google, Apple).
- **Firebase Identity Toolkit** — Password-reset email delivery via `send_password_reset_email`, with email-enumeration protection built in.

### PubMed (NCBI E-utilities)

- The **Experts** context queries the PubMed API (`esearch` + `efetch`) to retrieve peer-reviewed dermatology articles in real time.
- Results are filtered by category and cached in-process with a TTL to minimize upstream API calls.
- Author affiliations are parsed to extract country of origin when available.

---

## Project Structure

```
web-services/
├── main.py                        # FastAPI app factory, lifespan, middleware, router registration
├── Dockerfile                     # Cloud Run container (python:3.11-slim)
├── requirements.txt               # Pinned dependencies
├── .env                           # Local environment variables (git-ignored)
├── docs/
│   ├── architecture/              # Architectural decision records
│   ├── context/                   # Domain context documentation
│   └── specs/                     # Feature specifications
└── src/
    ├── core/
    │   ├── logger.py              # Centralized logger (stdout, Cloud Run compatible)
    │   ├── rate_limit.py          # SlowAPI limiter singleton (per-IP, opt-in)
    │   └── middlewares/
    │       └── jwt.py             # Global JWT extraction middleware
    └── features/
        ├── auth/
        │   ├── api/               # Router + Pydantic schemas
        │   ├── application/       # AuthService, ProfilePhotoService, PasswordResetService
        │   ├── domain/            # UserEntity, IAuthRepository, IUserRepository protocols
        │   └── infrastructure/    # FirebaseAuthAdapter, FirestoreUserAdapter, CloudStorageAdapter
        ├── detection/
        │   ├── api/               # Router + schemas (CreateScanRequest, ScanResponse, etc.)
        │   ├── application/       # ScanService
        │   ├── domain/            # ScanEntity, RiskLevel, BodyRegion, IScanRepository protocols
        │   └── infrastructure/    # FirestoreScanAdapter, CloudStorageScanAdapter, ACL/
        └── experts/
            ├── api/               # Router + ArticlesListResponse schema
            ├── application/       # ExpertsService (TTL-cached)
            ├── domain/            # ArticleEntity, ArticleCategory, IExpertsRepository protocol
            └── infrastructure/    # PubmedAdapter (httpx + E-utilities)
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- A GCP project with Firestore, Cloud Storage, and Firebase Auth enabled
- Firebase Admin SDK service account key (JSON)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd web-services

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### Running locally

```bash
# Set your Firebase credentials
set GOOGLE_APPLICATION_CREDENTIALS=path/to/firebase-adminsdk.json  # Windows
# export GOOGLE_APPLICATION_CREDENTIALS=path/to/firebase-adminsdk.json  # macOS / Linux

# Start development server
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

The interactive API docs are available at **http://localhost:8080/docs**.

---

## Deployment

The service is containerized and deployed to **Google Cloud Run**:

```bash
# Build the container
docker build -t skeen-backend .

# Run locally via Docker
docker run -p 8080:8080 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -v $(pwd)/credentials.json:/app/credentials.json \
  skeen-backend
```

Cloud Run deployment is handled via the GCP console or `gcloud run deploy`.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Firebase Admin SDK service account JSON | — |
| `FIRESTORE_DATABASE_ID` | Firestore database ID | `(default)` |
| `JWT_SECRET` | JWT signing secret (dev fallback) | `dev-secret-key` |

---

<p align="center">
  <sub>Built with ❤️ for dermatological health access in Peru</sub>
</p>
