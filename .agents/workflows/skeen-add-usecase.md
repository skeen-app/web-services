---
description: Creates the Domain Entity, Repository Interface, Application Service, and Infrastructure Implementation for a specific feature.
---
# skeen-add-usecase

## Goal
Enforce DDD patterns across layers automatically.

## Usage
Provide the `[context]` (e.g., patient, auth, detection, system) and `[name]` (e.g., CreatePatient).

## Steps
1. **Domain:** Create the Domain Entity and Repository Interface in `src/features/[context]/domain/`. No GCP dependencies.
2. **Application:** Create the Application Service (Use Case) in `src/features/[context]/application/`. Apply dependency injection.
3. **Infrastructure:** Create the Infrastructure Implementation in `src/features/[context]/infrastructure/` (e.g., Firestore implementation).
4. **API:** Ensure it connects to the FastAPI router.
