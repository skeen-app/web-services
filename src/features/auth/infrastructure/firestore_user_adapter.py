from firebase_admin import firestore
from src.features.auth.domain.entities import UserEntity

class FirestoreUserAdapter:
    def __init__(self):
        self.db = firestore.client()
        self.collection_name = "users"

    async def save_user(self, user: UserEntity) -> None:
        doc_ref = self.db.collection(self.collection_name).document(user.id)
        doc_ref.set(user.model_dump())

    async def get_user(self, user_id: str) -> UserEntity | None:
        doc_ref = self.db.collection(self.collection_name).document(user_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        return UserEntity(**doc.to_dict())
