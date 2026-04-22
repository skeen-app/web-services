# skeen - Backend DDD Rules

## Tech Stack
- Framework: FastAPI (Python 3.11+)
- Infrastructure: Google Cloud Platform (Cloud Run, Firestore, Storage)
- Auth: Firebase Admin SDK (JWT)
- Pattern: Domain-Driven Design (DDD)

## Token Optimization & AI Behavior
- **Think before acting.** Read `docs/` before proposing structural changes.
- **Concise output.** Only show relevant code diffs; avoid re-writing whole files.
- **Cache Ratio.** Suggest `/cost` if the session exceeds 20 turns.
- **Skip Large Files.** Ignore logs, lockfiles, or files >100KB.
- **Simple Solutions.** Avoid over-engineering; prioritize Pythonic, clean code.

## Coding Standards
- **Architecture:** Feature-first. Logic in `application`, data in `infrastructure`.
- **Patterns:** Use Singleton for DB clients and Repository pattern for data access.
- **Safety:** Pydantic for schemas/validation. No raw SQL (if any).