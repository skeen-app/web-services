from google.cloud import firestore
from src.features.auth.domain.entities import UserEntity
from src.core.logger import get_logger

logger = get_logger(__name__)

class FirestoreUserAdapter:
    def __init__(self, client: firestore.Client):
        self.db = client
        self.collection_name = "users"

    async def save_user(self, user: UserEntity) -> None:
        try:
            doc_ref = self.db.collection(self.collection_name).document(user.id)
            doc_ref.set(user.model_dump())
            logger.info(f"FirestoreUserAdapter: Saved user {user.id}")
        except Exception as e:
            logger.error(f"FirestoreUserAdapter: Failed to save user {user.id}. Error: {e}", exc_info=True)
            raise

    async def get_user(self, user_id: str) -> UserEntity | None:
        try:
            doc_ref = self.db.collection(self.collection_name).document(user_id)
            doc = doc_ref.get()
            if not doc.exists:
                logger.info(f"FirestoreUserAdapter: User {user_id} not found.")
                return None
            logger.info(f"FirestoreUserAdapter: Successfully retrieved user {user_id} from Firestore.")
            return UserEntity(**doc.to_dict())
        except Exception as e:
            logger.error(f"FirestoreUserAdapter: Failed to get user {user_id}. Error: {e}", exc_info=True)
            raise

    async def update_avatar_url(self, user_id: str, photo_url: str) -> None:
        try:
            doc_ref = self.db.collection(self.collection_name).document(user_id)
            doc_ref.update({"avatarUrl": photo_url})
            logger.info(f"FirestoreUserAdapter: Updated avatarUrl for user {user_id}")
        except Exception as e:
            logger.error(f"FirestoreUserAdapter: Failed to update avatarUrl for user {user_id}. Error: {e}", exc_info=True)
            raise

    async def update_profile(self, user_id: str, fields: dict) -> None:
        if not fields:
            return
        try:
            doc_ref = self.db.collection(self.collection_name).document(user_id)
            doc_ref.update(fields)
            logger.info(f"FirestoreUserAdapter: Updated profile fields for user {user_id}: {list(fields.keys())}")
        except Exception as e:
            logger.error(f"FirestoreUserAdapter: Failed to update profile for user {user_id}. Error: {e}", exc_info=True)
            raise

    async def set_active(self, user_id: str, is_active: bool, deactivated_at: int | None = None) -> None:
        try:
            doc_ref = self.db.collection(self.collection_name).document(user_id)
            payload: dict = {"isActive": is_active}
            # Stamp the deactivation moment for audit; keep it as `None` when
            # the user is being reactivated so we can tell the two states apart.
            payload["deactivatedAt"] = deactivated_at if not is_active else None
            doc_ref.update(payload)
            logger.info(f"FirestoreUserAdapter: set isActive={is_active} for user {user_id}")
        except Exception as e:
            logger.error(f"FirestoreUserAdapter: Failed to set isActive for user {user_id}. Error: {e}", exc_info=True)
            raise
