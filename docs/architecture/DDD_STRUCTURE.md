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
- **Anti-Corruption Layer (ACL):** Mandatory whenever a bounded context needs behavior that lives in another bounded context (see below).

## Bounded Context Boundaries

Each folder under `src/features/` is a **bounded context**. The following rules govern cross-context interactions:

1. **No direct imports from another context's `domain/` or `infrastructure/`.** A context's domain entities and adapters are private implementation details.
2. **Cross-context calls go through the Open Host Service** of the upstream context — i.e. a class in its `application/` layer that exposes a stable contract using its own published value objects (e.g., `AuthenticatedIdentity` in `auth/application/identity_service.py`).
3. **The downstream context owns the translation** via an Anti-Corruption Layer (ACL). The downstream defines a Port in its own `domain/` (e.g., `IIdentityValidator`) plus a local value object (e.g., `RequesterIdentity`), and an adapter in `infrastructure/acl/` translates the upstream model to the local one.
4. **Wiring lives only in the composition root** (the API router or `main.py`). Domain and application layers must depend on the Port, never on the upstream context.

### Currently Published Services

| Bounded Context | Published Service | Module |
|---|---|---|
| auth | `IdentityService` (`build_default_identity_service()` factory) | `src/features/auth/application/identity_service.py` |

### Anti-Corruption Layers in Place

| Consumer | Port (domain) | Adapter (infrastructure/acl) | Wraps |
|---|---|---|---|
| detection | `IIdentityValidator` → `RequesterIdentity` | `AuthIdentityACL` | `auth.IdentityService` |

### Folder Layout for a Context with an ACL

```
features/<context>/
├── domain/
│   └── entities.py          # local entities + repository Protocols + ACL Ports + cross-context VOs
├── application/
│   └── services.py          # depends on Ports only — never on other contexts
├── infrastructure/
│   ├── <persistence>_adapter.py
│   └── acl/
│       └── <other_context>_<purpose>_acl.py   # the ONLY file allowed to import from features.<other_context>
└── api/
    └── router.py            # composition root — wires the ACL via DI
```

### Example: Detection → Auth

`detection.api.router.get_requester` depends on `IIdentityValidator`. The Protocol is implemented by `AuthIdentityACL`, which calls `IdentityService.authenticate_bearer(...)` (Auth's published service) and translates `AuthenticatedIdentity` to Detection's `RequesterIdentity`. If Auth ever swaps Firebase for another provider, only the Auth context and the ACL change — Detection's domain, services, and router remain untouched.

### Adding a New Cross-Context Dependency — Checklist

1. Confirm the upstream context exposes a service in its `application/` layer (or add one).
2. In the consumer's `domain/entities.py`, add a Port (`Protocol`) + a local VO describing what the consumer needs.
3. In the consumer's `infrastructure/acl/`, add an adapter implementing the Port and translating to the local VO.
4. Wire the adapter in the consumer's composition root via `Depends(...)`.
5. Update the tables above in this file.
