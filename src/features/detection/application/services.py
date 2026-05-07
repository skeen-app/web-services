from datetime import datetime, timezone

from fastapi import HTTPException

from src.core.logger import get_logger
from src.features.detection.api.schemas import (
    ConfirmImageUploadRequest,
    CreateScanRequest,
    CreateScanResponse,
    DeleteScanResponse,
    ScanListResponse,
    ScanResponse,
    ScanStatsResponse,
)
from src.features.detection.domain.entities import (
    BodyRegion,
    IScanRepository,
    IScanStorageRepository,
    ScanEntity,
)

logger = get_logger(__name__)


# Mapping used by the home dashboard body-map bars (head/chest/legs).
_REGION_TO_GROUP: dict[BodyRegion, str] = {
    BodyRegion.HEAD: "head",
    BodyRegion.NECK: "head",
    BodyRegion.CHEST: "chest",
    BodyRegion.BACK: "chest",
    BodyRegion.ABDOMEN: "chest",
    BodyRegion.LEFT_ARM: "chest",
    BodyRegion.RIGHT_ARM: "chest",
    BodyRegion.LEFT_LEG: "legs",
    BodyRegion.RIGHT_LEG: "legs",
}


class ScanService:
    """Application service orchestrating scan persistence + image upload."""

    SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

    def __init__(
        self,
        scan_repo: IScanRepository,
        storage_repo: IScanStorageRepository,
    ):
        self.scan_repo = scan_repo
        self.storage_repo = storage_repo

    # ── Create ────────────────────────────────────────────────────────

    async def create_scan(
        self,
        user_id: str,
        request: CreateScanRequest,
    ) -> CreateScanResponse:
        logger.info(
            f"ScanService: creating scan {request.id} for user {user_id} "
            f"(label={request.top_label}, region={request.body_region})"
        )

        if request.has_image:
            content_type = request.image_content_type or "image/jpeg"
            if content_type not in self.SUPPORTED_IMAGE_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported image content type: {content_type}",
                )
            upload_url, object_path = await self.storage_repo.issue_upload_url(
                user_id=user_id,
                scan_id=request.id,
                content_type=content_type,
            )
        else:
            upload_url = None
            object_path = None

        now = datetime.now(tz=timezone.utc)
        entity = ScanEntity(
            id=request.id,
            user_id=user_id,
            top_label=request.top_label,
            confidence=request.confidence,
            risk_level=request.risk_level,
            body_region=request.body_region,
            body_part_label=request.body_part_label,
            captured_at=request.captured_at,
            distance_cm=request.distance_cm,
            image_hash=request.image_hash,
            image_object_path=object_path,
            # ``image_uploaded`` flips to True via ``confirm_image_upload``
            # once the client confirms the PUT succeeded.
            image_uploaded=False,
            relative_position_x=request.relative_position_x,
            relative_position_y=request.relative_position_y,
            created_at=now,
            updated_at=now,
        )
        await self.scan_repo.save(entity)

        return CreateScanResponse(
            scan=await self._to_response(entity, with_download=False),
            image_upload_url=upload_url,
            image_object_path=object_path,
        )

    # ── Confirm upload ────────────────────────────────────────────────

    async def confirm_image_upload(
        self,
        user_id: str,
        scan_id: str,
        request: ConfirmImageUploadRequest,
    ) -> ScanResponse:
        scan = await self.scan_repo.find_by_id(user_id, scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")

        await self.scan_repo.mark_image_uploaded(
            user_id=user_id,
            scan_id=scan_id,
            object_path=request.object_path,
        )
        scan.image_object_path = request.object_path
        scan.image_uploaded = True
        scan.updated_at = datetime.now(tz=timezone.utc)
        return await self._to_response(scan, with_download=True)

    # ── Read ──────────────────────────────────────────────────────────

    async def list_scans(self, user_id: str) -> ScanListResponse:
        scans = await self.scan_repo.find_by_user(user_id)
        items = [await self._to_response(s, with_download=False) for s in scans]
        return ScanListResponse(items=items, total=len(items))

    async def get_scan(self, user_id: str, scan_id: str) -> ScanResponse:
        scan = await self.scan_repo.find_by_id(user_id, scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        return await self._to_response(scan, with_download=True)

    async def get_stats(self, user_id: str) -> ScanStatsResponse:
        scans = await self.scan_repo.find_by_user(user_id)
        by_group: dict[str, int] = {"head": 0, "chest": 0, "legs": 0}
        for s in scans:
            if s.body_region is None:
                continue
            group = _REGION_TO_GROUP.get(s.body_region)
            if group:
                by_group[group] += 1
        return ScanStatsResponse(total=len(scans), by_group=by_group)

    # ── Delete ────────────────────────────────────────────────────────

    async def delete_scan(self, user_id: str, scan_id: str) -> DeleteScanResponse:
        scan = await self.scan_repo.find_by_id(user_id, scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        if scan.image_object_path:
            try:
                await self.storage_repo.delete_object(scan.image_object_path)
            except Exception:
                # Storage cleanup is best-effort; we still want the doc gone.
                logger.warning(
                    f"ScanService: failed to delete blob for scan {scan_id} — "
                    "Firestore document will still be removed."
                )
        deleted = await self.scan_repo.delete(user_id, scan_id)
        return DeleteScanResponse(deleted=deleted, id=scan_id)

    # ── Helpers ───────────────────────────────────────────────────────

    async def _to_response(
        self,
        scan: ScanEntity,
        *,
        with_download: bool,
    ) -> ScanResponse:
        download_url = None
        if (
            with_download
            and scan.image_uploaded
            and scan.image_object_path
        ):
            try:
                download_url = await self.storage_repo.issue_download_url(
                    scan.image_object_path
                )
            except Exception as e:
                logger.warning(
                    f"ScanService: failed to mint download URL for {scan.id}: {e}"
                )
        return ScanResponse(
            id=scan.id,
            user_id=scan.user_id,
            top_label=scan.top_label,
            confidence=scan.confidence,
            risk_level=scan.risk_level,
            body_region=scan.body_region,
            body_part_label=scan.body_part_label,
            captured_at=scan.captured_at,
            distance_cm=scan.distance_cm,
            image_hash=scan.image_hash,
            image_object_path=scan.image_object_path,
            image_uploaded=scan.image_uploaded,
            image_download_url=download_url,
            relative_position_x=scan.relative_position_x,
            relative_position_y=scan.relative_position_y,
            created_at=scan.created_at,
            updated_at=scan.updated_at,
        )
