from pydantic import BaseModel

class UserEntity(BaseModel):
    id: str
    email: str
    role: str
