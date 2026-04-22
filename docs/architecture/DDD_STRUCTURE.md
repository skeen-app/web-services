# Backend DDD Architecture

## Layers Definition
- **Domain:** Pure logic. Entities and Repository Interfaces. No dependencies on GCP libraries here.
- **Application:** The "Orchestrator". Use Cases (Services) that call repositories and external services.
- **Infrastructure:** The implementation of repositories (Firestore, Storage) and external API adapters.
- **API (Interface):** FastAPI routers, request/response schemas (Pydantic).

## Design Patterns
- **Singleton:** For Firestore, Secret Manager, and Storage clients.
- **Dependency Injection:** Inject repositories into Services/Use Cases.
- **Repository Pattern:** Abstract all data access.