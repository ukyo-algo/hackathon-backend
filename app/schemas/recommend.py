from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class RecommendItem(BaseModel):
    item_id: str
    name: str
    price: Optional[int] = None
    image_url: Optional[str] = None
    description: Optional[str] = None


class RecommendRequest(BaseModel):
    user_id: str
    mode: str  # "history" or "keyword"
    keyword: Optional[str] = None


class RecommendResponse(BaseModel):
    can_recommend: bool
    persona_question: str
    message: str
    items: List[RecommendItem]
    persona: Dict[str, Any]
    reason: Optional[str] = None


class RecommendHistoryItem(BaseModel):
    """おすすめ履歴の1件"""
    id: int
    item_id: str
    name: str
    price: Optional[int] = None
    image_url: Optional[str] = None
    status: Optional[str] = None  # 'on_sale' or 'sold'
    reason: Optional[str] = None
    persona_name: Optional[str] = None  # おすすめを生成したペルソナ名
    persona_avatar_url: Optional[str] = None  # ペルソナのアバター画像URL
    interest: Optional[str] = None
    recommended_at: str

    class Config:
        from_attributes = True

