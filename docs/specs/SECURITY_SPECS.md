# Security & Protection Specs

## 1. Identity & JWT
- **Mechanism:** Firebase Auth JWT Verification.
- **Implementation:** Middleware that extracts Bearer token and verifies via Firebase Admin SDK.
- **Requirement:** Every request must be authenticated unless marked as public.

## 2. OWASP Top 10 Mitigations (Mobile Focus)
- **M1 (Improper Platform Usage):** Validation of App Check tokens (optional) and strict CORS.
- **M2 (Insecure Data Storage):** No sensitive data in logs. Use Secret Manager for environment keys.
- **M3 (Insecure Communication):** Enforce HTTPS/TLS 1.3.
- **M4 (Insecure Authentication):** Rate limiting on auth endpoints.

## 3. Attack Mitigations
- **SQLi/NoSQLi:** Use Pydantic and Firestore ODM to prevent injection.
- **DDoS/Rate Limit:** Implement `slowapi` or similar to limit requests per IP/User.
- **Data Sanitization:** Strict input validation on every endpoint.

## 4. Error Handling & API Design
- **Clean Architected Responses:** Every API router must contain a robust `try-catch` block mapping errors to standard HTTP Status Codes.
- **No Stack Traces:** Internal server errors (500) must obscure detailed engine stack lines to prevent data leakage.
- **Client Errors:** Correct usage of 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), and 404 (Not Found).

## 5. Observability & Traceability
- **Mandatory Logging:** All new endpoints, application services, and infrastructure adapters MUST use the centralized logger from `src.core.logger`.
- **Traceability:** Logs should include relevant context (e.g., user IDs, event types) but NEVER sensitive PII or secrets.
- **Severity Levels:** Use `INFO` for normal flow, `WARNING` for handled issues, and `ERROR` (with `exc_info=True`) for unhandled exceptions.