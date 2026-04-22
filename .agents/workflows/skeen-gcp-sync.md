---
description: Generates or updates the infrastructure layer adapters for Firestore, Secret Manager, or Cloud Storage.
---
# skeen-gcp-sync

## Goal
Ensure consistent usage of GCP Singletons.

## Steps
1. Review or generate Singleton patterns for GCP resources.
2. Ensure Firestore uses NoSQL documents and collections matching Bounded Contexts.
3. Update `src/core/gcp/` to hold shared adapters if needed or place them in appropriate infrastructure layers.
