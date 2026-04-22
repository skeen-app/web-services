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