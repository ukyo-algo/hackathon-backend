from pydantic import BaseModel
from typing import List, Optional


class RecommendItem(BaseModel):
    id: int
    title: str
    price: Optional[int] = None
    image_url: Optional[str] = None


class RecommendRequest(BaseModel):
    user_id: str
    mode: str  # "history" or "keyword"
    keyword: Optional[str] = None


class RecommendResponse(BaseModel):
    can_recommend: bool
    persona_question: str
    items: List[RecommendItem]
    persona: dict
    reason: Optional[str] = None
