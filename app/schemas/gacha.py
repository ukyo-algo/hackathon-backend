# hackathon-backend/app/schemas/gacha.py
from pydantic import BaseModel
from app.schemas.user import PersonaBase


class GachaResponse(BaseModel):
    persona: PersonaBase
    is_new: bool
    stack_count: int
    message: str
