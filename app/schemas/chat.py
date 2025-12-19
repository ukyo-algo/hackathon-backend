# hackathon-backend/app/schemas/chat.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """チャットリクエスト"""
    message: str
    page_context: Optional[Dict[str, Any]] = None  # ページコンテキスト
    history: Optional[List[Dict[str, Any]]] = None  # 互換性維持（未使用）


class ChatResponse(BaseModel):
    """チャットレスポンス"""
    reply: str
    persona: Dict[str, Any]
    function_calls: Optional[List[Dict[str, Any]]] = None


class ChatMessageCreate(BaseModel):
    """チャットメッセージ保存リクエスト"""
    role: str  # 'user' or 'ai'
    content: str
    type: Optional[str] = None  # 'guidance', 'chat', etc.
    page_path: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """チャットメッセージレスポンス"""
    id: int
    role: str
    content: str
    type: Optional[str]
    page_path: Optional[str]
    persona_name: Optional[str]
    is_visible: bool = True
    created_at: str

    class Config:
        from_attributes = True


class ImageAnalysisRequest(BaseModel):
    """画像解析リクエスト"""
    image_base64: str  # Base64エンコードされた画像
    prompt: Optional[str] = None  # 追加の指示（オプション）


class ImageAnalysisResponse(BaseModel):
    """画像解析レスポンス"""
    name: Optional[str] = None
    category: Optional[str] = None
    condition: Optional[str] = None
    suggested_price: Optional[int] = None
    price_range: Optional[Dict[str, int]] = None
    description: Optional[str] = None
    message: str
