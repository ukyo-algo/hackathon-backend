# hackathon-backend/app/schemas/gacha.py
from pydantic import BaseModel
from app.schemas.user import PersonaBase


class GachaResponse(BaseModel):
    persona: PersonaBase
    is_new: bool
    stack_count: int
    message: str
    discount_applied: int = 0  # Added field to match backend implementation
    fragments_earned: int = 0
    total_memory_fragments: int = 0
    cost: int = 0


class ChargeRequest(BaseModel):
    amount: int
    payment_method: str  # credit_card, bank_transfer, cod


class ChargeResponse(BaseModel):
    success: bool
    added_points: int
    current_points: int
    message: str
