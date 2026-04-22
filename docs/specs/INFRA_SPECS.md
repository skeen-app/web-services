# GCP Infrastructure Integration

## 1. Serverless Deployment
- **Target:** Google Cloud Run (Docker Container).
- **Configuration:** Stateless instance. Use `google-cloud-logging` for telemetry.

## 2. Persistence (Firestore)
- **Pattern:** NoSQL Documents.
- **Collections:** Match Bounded Contexts (patients, analysis_results, sessions).
- **Access:** Use `google-cloud-firestore` with Singleton pattern.

## 3. Storage & Secrets
- **Cloud Storage:** Asynchronous upload/download of lesion images.
- **Secret Manager:** All API keys, Firebase service accounts, and model versions must be fetched via `google-cloud-secret-manager`.

## 4. AI Orchestration
- **TFLite:** Backend serves model metadata and orchestrates versioning for OTA updates.