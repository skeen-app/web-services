# Claude Code Backend Skills

## Automation Macros

1. **`skeen-init-backend`**
   - **Action:** Initializes the FastAPI boilerplate, Dockerfile, and the 4 bounded context directories.
   - **Goal:** Quick start without re-explaining the DDD structure.

2. **`skeen-add-usecase [context] [name]`**
   - **Action:** Creates the Domain Entity, Repository Interface, Application Service, and Infrastructure Implementation for a specific feature.
   - **Goal:** Enforce DDD patterns across layers automatically.

3. **`skeen-secure-audit`**
   - **Action:** Scans the current feature for OWASP Top 10 vulnerabilities (check for missing JWT validation, raw inputs, or insecure error messages).
   - **Goal:** Maintain high security standards in every Pull Request.

4. **`skeen-gcp-sync`**
   - **Action:** Generates or updates the `infrastructure` layer adapters for Firestore, Secret Manager, or Cloud Storage.
   - **Goal:** Ensure consistent usage of GCP Singletons.

5. **`skeen-brief-be`**
   - **Action:** Summarizes the API routes and current entity relationships into a temporary file to reduce context window usage.
   - **Goal:** Token optimization during long development sessions.