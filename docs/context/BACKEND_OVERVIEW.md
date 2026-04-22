# Backend Project Overview: skeen

## Vision
The skeen backend acts as a robust, secure, and highly scalable orchestrator for dermatological triage data in Peru. Its primary role is to manage clinical metadata, secure identities, and ensure the mobile fleet has the latest AI models and configurations.

## Architecture Mission
- **Centralized Clinical Registry:** Securely store patient data and analysis results.
- **Trusted Identity:** Delegate authentication to Firebase Auth while managing internal session policies.
- **Asset Hub:** Coordinate Over-the-Air (OTA) updates for TFLite models and AR assets via GCP.
- **On-Device Synergy:** Support the mobile app's 100% local inference by providing a reliable sync and backup layer.

## Bounded Contexts (Backend Logic)

1. **Identity Validation (Auth)**
   - Token verification (Firebase JWT).
   - Professional profile management.
   - Audit logs for sensitive data access.

2. **Patient Data Management (Patient)**
   - NoSQL schemas for Patient metadata.
   - History of analysis results linked to specific dermatological cases.
   - PII (Personally Identifiable Information) encryption at the application level.

3. **Inference Coordination (Detection)**
   - Receiving and storing analysis metadata (labels, confidence scores).
   - Managing Cloud Storage signed URLs for lesion image backups (for doctor review).

4. **OTA Update Orchestration (System)**
   - Model version control.
   - Serving manifests for AR assets and TFLite updates.