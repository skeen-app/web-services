from datetime import datetime

from pydantic import BaseModel, Field

from src.features.detection.domain.entities import BodyRegion, RiskLevel


# ── Inbound schemas ───────────────────────────────────────────────────


class CreateScanRequest(BaseModel):
    """Payload to register a scan analysis.

    The image itself is NOT uploaded here — the response carries a signed
    URL the client uses to PUT the (re-encrypted) JPEG straight to Cloud
    Storage.
    """

    id: str = Field(..., description="Client UUID — used as the Firestore doc id.")
    top_label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    body_region: BodyRegion | None = None
    body_part_label: str | None = Field(default=None, max_length=80)
    captured_at: datetime
    distance_cm: float | None = None
    image_hash: str | None = None
    relative_position_x: float | None = Field(default=None, ge=0.0, le=1.0)
    relative_position_y: float | None = Field(default=None, ge=0.0, le=1.0)
    has_image: bool = Field(
        default=True,
        description="Whether the client intends to upload an image.",
    )
    image_content_type: str | None = Field(
        default="image/jpeg",
        description="MIME type the client will PUT (jpeg/png/webp).",
    )


class ConfirmImageUploadRequest(BaseModel):
    """Sent after the client successfully PUTs to the signed URL."""

    object_path: str


# ── Outbound schemas ──────────────────────────────────────────────────


class ScanResponse(BaseModel):
    id: str
    user_id: str
    top_label: str
    confidence: float
    risk_level: RiskLevel
    body_region: BodyRegion | None = None
    body_part_label: str | None = None
    captured_at: datetime
    distance_cm: float | None = None
    image_hash: str | None = None
    image_object_path: str | None = None
    image_uploaded: bool
    image_download_url: str | None = Field(
        default=None,
        description="Time-limited signed URL the client can use to fetch the image.",
    )
    relative_position_x: float | None = None
    relative_position_y: float | None = None
    created_at: datetime
    updated_at: datetime


class CreateScanResponse(BaseModel):
    scan: ScanResponse
    image_upload_url: str | None = Field(
        default=None,
        description="Signed PUT URL — null when has_image=False.",
    )
    image_object_path: str | None = None


class ScanListResponse(BaseModel):
    items: list[ScanResponse]
    total: int


class ScanStatsResponse(BaseModel):
    """Aggregate counts surfaced on the home dashboard body map."""

    total: int
    by_group: dict[str, int]  # 'head' | 'chest' | 'legs' → count


class DeleteScanResponse(BaseModel):
    deleted: bool
    id: str


__all__ = [
    "CreateScanRequest",
    "ConfirmImageUploadRequest",
    "ScanResponse",
    "CreateScanResponse",
    "ScanListResponse",
    "ScanStatsResponse",
    "DeleteScanResponse",
]
