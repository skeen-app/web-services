import os
from google.cloud import storage
from src.core.logger import get_logger

logger = get_logger(__name__)

# Mapping from MIME type to file extension
_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class CloudStorageAdapter:
    """Infrastructure adapter for Google Cloud Storage — profile photo uploads."""

    def __init__(self, client: storage.Client):
        self.client = client
        self.bucket_name = os.getenv("GCS_PROFILE_PHOTOS_BUCKET", "skeen-profile-photos")

    async def upload_profile_photo(self, user_id: str, file_content: bytes, content_type: str) -> str:
        """
        Upload profile photo bytes to Cloud Storage and return the public URL.
        The object path follows: profiles/{user_id}.{ext}
        Re-uploading overwrites the previous photo automatically.
        """
        ext = _MIME_TO_EXT.get(content_type, "jpg")
        blob_path = f"profiles/{user_id}.{ext}"

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_path)
            blob.cache_control = "no-cache, max-age=0"
            blob.upload_from_string(file_content, content_type=content_type)

            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"
            logger.info(f"CloudStorageAdapter: Uploaded profile photo for user {user_id} -> {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"CloudStorageAdapter: Failed to upload photo for user {user_id}. Error: {e}", exc_info=True)
            raise
