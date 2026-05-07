from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from src.core.logger import get_logger
from src.features.auth.application.identity_service import (
    build_default_identity_service,
)
from src.features.detection.api.schemas import (
    ConfirmImageUploadRequest,
    CreateScanRequest,
    CreateScanResponse,
    DeleteScanResponse,
    ScanListResponse,
    ScanResponse,
    ScanStatsResponse,
)
from src.features.detection.application.services import ScanService
from src.features.detection.domain.entities import (
    IIdentityValidator,
    RequesterIdentity,
)
from src.features.detection.infrastructure.acl.auth_identity_acl import (
    AuthIdentityACL,
)
from src.features.detection.infrastructure.cloud_storage_scan_adapter import (
    CloudStorageScanAdapter,
)
from src.features.detection.infrastructure.firestore_scan_adapter import (
    FirestoreScanAdapter,
)

logger = get_logger(__name__)
router = APIRouter()


# ── DI ────────────────────────────────────────────────────────────────


def get_identity_validator() -> IIdentityValidator:
    # Composition root for the ACL: Auth's published service is wrapped
    # by Detection's adapter. Only this wiring touches `features.auth`,
    # and only via Auth's published application factory.
    return AuthIdentityACL(build_default_identity_service())


async def get_requester(
    authorization: str | None = Header(default=None),
    validator: IIdentityValidator = Depends(get_identity_validator),
) -> RequesterIdentity:
    return await validator.resolve_from_authorization(authorization)


def get_scan_service(request: Request) -> ScanService:
    scan_repo = FirestoreScanAdapter(client=request.app.state.firestore_client)
    storage_repo = CloudStorageScanAdapter(client=request.app.state.storage_client)
    return ScanService(scan_repo, storage_repo)


# ── Routes ────────────────────────────────────────────────────────────


@router.post("", response_model=CreateScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    request: CreateScanRequest,
    requester: RequesterIdentity = Depends(get_requester),
    service: ScanService = Depends(get_scan_service),
):
    try:
        logger.info(
            f"POST /scans by user {requester.uid} (scan_id={request.id})"
        )
        return await service.create_scan(user_id=requester.uid, request=request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /scans failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register scan.",
        )


@router.post("/{scan_id}/image", response_model=ScanResponse)
async def confirm_image_upload(
    scan_id: str,
    payload: ConfirmImageUploadRequest,
    requester: RequesterIdentity = Depends(get_requester),
    service: ScanService = Depends(get_scan_service),
):
    try:
        logger.info(f"POST /scans/{scan_id}/image by user {requester.uid}")
        return await service.confirm_image_upload(requester.uid, scan_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /scans/{scan_id}/image failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm image upload.",
        )


@router.get("", response_model=ScanListResponse)
async def list_scans(
    requester: RequesterIdentity = Depends(get_requester),
    service: ScanService = Depends(get_scan_service),
):
    try:
        return await service.list_scans(requester.uid)
    except Exception as e:
        logger.error(f"GET /scans failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load scans.",
        )


@router.get("/stats", response_model=ScanStatsResponse)
async def get_scan_stats(
    requester: RequesterIdentity = Depends(get_requester),
    service: ScanService = Depends(get_scan_service),
):
    try:
        return await service.get_stats(requester.uid)
    except Exception as e:
        logger.error(f"GET /scans/stats failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute scan stats.",
        )


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: str,
    requester: RequesterIdentity = Depends(get_requester),
    service: ScanService = Depends(get_scan_service),
):
    try:
        return await service.get_scan(requester.uid, scan_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /scans/{scan_id} failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load scan.",
        )


@router.delete("/{scan_id}", response_model=DeleteScanResponse)
async def delete_scan(
    scan_id: str,
    requester: RequesterIdentity = Depends(get_requester),
    service: ScanService = Depends(get_scan_service),
):
    try:
        return await service.delete_scan(requester.uid, scan_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DELETE /scans/{scan_id} failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scan.",
        )
