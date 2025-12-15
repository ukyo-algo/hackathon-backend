from pydantic import BaseModel
from typing import Optional


class RewardClaimRequest(BaseModel):
    user_id: str  # firebase_uid


class RewardClaimResponse(BaseModel):
    granted: bool
    amount: int
    coins: int
    next_claim_at: Optional[str] = None  # ISO8601文字列
    reason: Optional[str] = None
