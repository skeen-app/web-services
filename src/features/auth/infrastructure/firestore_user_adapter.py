from firebase_admin import firestore
from src.features.auth.domain.entities import UserEntity
from src.core.logger import get_logger

logger = get_logger(__name__)

class FirestoreUserAdapter:
    def __init__(self):
        self.db = firestore.client()
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
