from datetime import datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field


# ── Domain enums ──────────────────────────────────────────────────────


class RiskLevel(str, Enum):
    """User-facing risk bucket (matches mobile `WarningLevel`)."""

    LOW = "low"  # reassuring
    MEDIUM = "medium"  # caution
    HIGH = "high"  # alert


class BodyRegion(str, Enum):
    """Coarse anatomical region selected by the user post-capture.

    Mirrors the Flutter `BodyRegion` enum so the wire format is identical.
    """

    HEAD = "head"
    NECK = "neck"
    CHEST = "chest"
    BACK = "back"
    LEFT_ARM = "leftArm"
    RIGHT_ARM = "rightArm"
    ABDOMEN = "abdomen"
    LEFT_LEG = "leftLeg"
    RIGHT_LEG = "rightLeg"


# ── Aggregate root ────────────────────────────────────────────────────


class ScanEntity(BaseModel):
    """One persisted scan analysis tied to a user.

    Stored anonymously — only the AI metadata + a Cloud Storage pointer to
    the (re-encrypted) image. The user binding is the Firestore document's
    parent `users/{uid}/scans` path; no PII lives in the document body
    itself.
    """

    id: str = Field(..., description="Client-generated UUID — also Firestore doc id.")
    user_id: str
    top_label: str = Field(..., description="ClassLabel slug (e.g., 'melanoma').")
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    body_region: BodyRegion | None = None
    body_part_label: str | None = Field(
        default=None,
        description=(
            "Free-form, more specific anatomical label entered by the user "
            "(e.g., 'Upper Back')."
        ),
    )
    captured_at: datetime
    distance_cm: float | None = None
    image_hash: str | None = Field(
        default=None,
        description="SHA-256 of the plaintext JPEG before re-encryption.",
    )
    image_object_path: str | None = Field(
        default=None,
        description="GCS object path (e.g., scans/{uid}/{scan_id}.jpg). Set after upload.",
    )
    image_uploaded: bool = False
    relative_position_x: float | None = Field(default=None, ge=0.0, le=1.0)
    relative_position_y: float | None = Field(default=None, ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime


# ── Repository interfaces ─────────────────────────────────────────────


class IScanRepository(Protocol):
    async def save(self, scan: ScanEntity) -> None:
        """Upsert a scan document under users/{user_id}/scans/{scan_id}."""
        ...

    async def find_by_id(self, user_id: str, scan_id: str) -> ScanEntity | None:
        ...

    async def find_by_user(
        self,
        user_id: str,
        limit: int | None = None,
    ) -> list[ScanEntity]:
        ...

    async def delete(self, user_id: str, scan_id: str) -> bool:
        """Returns True when an existing doc was removed, False when missing."""
        ...

    async def mark_image_uploaded(self, user_id: str, scan_id: str, object_path: str) -> None:
        ...


class IScanStorageRepository(Protocol):
    async def issue_upload_url(
        self,
        user_id: str,
        scan_id: str,
        content_type: str,
    ) -> tuple[str, str]:
        """Returns ``(signed_put_url, object_path)``.

        The mobile client PUTs the (re-encrypted) JPEG directly to this URL
        — the API never receives the blob, so Cloud Run stays cheap and
        bandwidth is bounded.
        """
        ...

    async def issue_download_url(self, object_path: str) -> str:
        """Time-limited signed URL the mobile client can fetch the image with."""
        ...

    async def delete_object(self, object_path: str) -> None:
        ...


# ── ACL ports (cross-context) ─────────────────────────────────────────


class RequesterIdentity(BaseModel):
    """Detection-local view of the authenticated caller.

    Detection only needs to know *who* is making the request — never the
    underlying token format. The concrete shape lives here so the
    Anti-Corruption Layer can evolve the upstream Auth model without
    leaking changes into Detection's domain or services.
    """

    uid: str


class IIdentityValidator(Protocol):
    """Detection's port for resolving an HTTP caller into a domain identity.

    Implemented by an ACL adapter that wraps the Auth bounded context's
    public ``IdentityService``. Keeping the Protocol in this domain
    package guarantees that Detection's services depend only on
    Detection's own abstractions.
    """

    async def resolve_from_authorization(
        self, authorization_header: str | None
    ) -> RequesterIdentity:
        ...
