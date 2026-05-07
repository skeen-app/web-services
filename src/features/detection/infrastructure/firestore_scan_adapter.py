from datetime import datetime, timezone

from google.cloud import firestore

from src.core.logger import get_logger
from src.features.detection.domain.entities import (
    BodyRegion,
    RiskLevel,
    ScanEntity,
)

logger = get_logger(__name__)


class FirestoreScanAdapter:
    """Persists scan analyses under ``users/{user_id}/scans/{scan_id}``.

    Subcollection layout — keeps Firestore security rules trivially
    user-scoped: a user can only ever read/write under their own document.
    """

    USERS_COLLECTION = "users"
    SCANS_SUBCOLLECTION = "scans"

    def __init__(self, client: firestore.Client):
        self.db = client

    # ── Helpers ───────────────────────────────────────────────────────

    def _scans_ref(self, user_id: str):
        return (
            self.db.collection(self.USERS_COLLECTION)
            .document(user_id)
            .collection(self.SCANS_SUBCOLLECTION)
        )

    @staticmethod
    def _to_entity(user_id: str, scan_id: str, data: dict) -> ScanEntity:
        return ScanEntity(
            id=scan_id,
            user_id=user_id,
            top_label=data["top_label"],
            confidence=float(data["confidence"]),
            risk_level=RiskLevel(data["risk_level"]),
            body_region=BodyRegion(data["body_region"]) if data.get("body_region") else None,
            body_part_label=data.get("body_part_label"),
            captured_at=data["captured_at"],
            distance_cm=data.get("distance_cm"),
            image_hash=data.get("image_hash"),
            image_object_path=data.get("image_object_path"),
            image_uploaded=bool(data.get("image_uploaded", False)),
            relative_position_x=data.get("relative_position_x"),
            relative_position_y=data.get("relative_position_y"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    # ── CRUD ──────────────────────────────────────────────────────────

    async def save(self, scan: ScanEntity) -> None:
        try:
            doc_ref = self._scans_ref(scan.user_id).document(scan.id)
            payload = {
                "top_label": scan.top_label,
                "confidence": scan.confidence,
                "risk_level": scan.risk_level.value,
                "body_region": scan.body_region.value if scan.body_region else None,
                "body_part_label": scan.body_part_label,
                "captured_at": scan.captured_at,
                "distance_cm": scan.distance_cm,
                "image_hash": scan.image_hash,
                "image_object_path": scan.image_object_path,
                "image_uploaded": scan.image_uploaded,
                "relative_position_x": scan.relative_position_x,
                "relative_position_y": scan.relative_position_y,
                "created_at": scan.created_at,
                "updated_at": scan.updated_at,
            }
            doc_ref.set(payload, merge=True)
            logger.info(
                f"FirestoreScanAdapter: saved scan {scan.id} for user {scan.user_id}"
            )
        except Exception as e:
            logger.error(
                f"FirestoreScanAdapter: failed to save scan {scan.id}: {e}",
                exc_info=True,
            )
            raise

    async def find_by_id(self, user_id: str, scan_id: str) -> ScanEntity | None:
        try:
            doc = self._scans_ref(user_id).document(scan_id).get()
            if not doc.exists:
                return None
            return self._to_entity(user_id, scan_id, doc.to_dict())
        except Exception as e:
            logger.error(
                f"FirestoreScanAdapter: failed to read scan {scan_id}: {e}",
                exc_info=True,
            )
            raise

    async def find_by_user(
        self,
        user_id: str,
        limit: int | None = None,
    ) -> list[ScanEntity]:
        try:
            query = self._scans_ref(user_id).order_by(
                "captured_at", direction=firestore.Query.DESCENDING
            )
            if limit is not None:
                query = query.limit(limit)
            return [
                self._to_entity(user_id, doc.id, doc.to_dict())
                for doc in query.stream()
            ]
        except Exception as e:
            logger.error(
                f"FirestoreScanAdapter: failed to list scans for {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, user_id: str, scan_id: str) -> bool:
        try:
            ref = self._scans_ref(user_id).document(scan_id)
            snapshot = ref.get()
            if not snapshot.exists:
                return False
            ref.delete()
            logger.info(
                f"FirestoreScanAdapter: deleted scan {scan_id} for user {user_id}"
            )
            return True
        except Exception as e:
            logger.error(
                f"FirestoreScanAdapter: failed to delete scan {scan_id}: {e}",
                exc_info=True,
            )
            raise

    async def mark_image_uploaded(
        self, user_id: str, scan_id: str, object_path: str
    ) -> None:
        try:
            self._scans_ref(user_id).document(scan_id).update(
                {
                    "image_object_path": object_path,
                    "image_uploaded": True,
                    "updated_at": datetime.now(tz=timezone.utc),
                }
            )
            logger.info(
                f"FirestoreScanAdapter: marked scan {scan_id} as uploaded ({object_path})"
            )
        except Exception as e:
            logger.error(
                f"FirestoreScanAdapter: failed to mark uploaded {scan_id}: {e}",
                exc_info=True,
            )
            raise
