import os
from datetime import timedelta

from google.cloud import storage

from src.core.logger import get_logger

logger = get_logger(__name__)


_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class CloudStorageScanAdapter:
    """Issues V4 signed URLs so the mobile client can PUT/GET scan images
    directly against Cloud Storage. The API never proxies the image bytes
    — keeps Cloud Run's bandwidth bounded and the request latency low.
    """

    UPLOAD_URL_LIFETIME = timedelta(minutes=15)
    DOWNLOAD_URL_LIFETIME = timedelta(hours=1)

    def __init__(self, client: storage.Client):
        self.client = client
        self.bucket_name = os.getenv("GCS_SCAN_IMAGES_BUCKET", "skeen-scan-images")

    # ── Path helpers ──────────────────────────────────────────────────

    @staticmethod
    def _object_path(user_id: str, scan_id: str, content_type: str) -> str:
        ext = _MIME_TO_EXT.get(content_type, "jpg")
        # Layout: scans/{uid}/{scan_id}.{ext}
        # The blob is anonymous from the user's PoV — only the auth-server
        # ever resolves uid → email.
        return f"scans/{user_id}/{scan_id}.{ext}"

    # ── Public API ────────────────────────────────────────────────────

    async def issue_upload_url(
        self,
        user_id: str,
        scan_id: str,
        content_type: str,
    ) -> tuple[str, str]:
        try:
            bucket = self.client.bucket(self.bucket_name)
            object_path = self._object_path(user_id, scan_id, content_type)
            blob = bucket.blob(object_path)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=self.UPLOAD_URL_LIFETIME,
                method="PUT",
                content_type=content_type,
            )
            logger.info(
                f"CloudStorageScanAdapter: issued upload URL for {object_path} "
                f"(expires in {int(self.UPLOAD_URL_LIFETIME.total_seconds())}s)"
            )
            return signed_url, object_path
        except Exception as e:
            logger.error(
                f"CloudStorageScanAdapter: failed to issue upload URL: {e}",
                exc_info=True,
            )
            raise

    async def issue_download_url(self, object_path: str) -> str:
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(object_path)
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=self.DOWNLOAD_URL_LIFETIME,
                method="GET",
            )
            return signed_url
        except Exception as e:
            logger.error(
                f"CloudStorageScanAdapter: failed to issue download URL: {e}",
                exc_info=True,
            )
            raise

    async def delete_object(self, object_path: str) -> None:
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(object_path)
            if blob.exists():
                blob.delete()
                logger.info(f"CloudStorageScanAdapter: deleted {object_path}")
        except Exception as e:
            logger.error(
                f"CloudStorageScanAdapter: failed to delete {object_path}: {e}",
                exc_info=True,
            )
            raise
