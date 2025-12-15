# hackathon-backend/app/schemas/chat.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = None  # 互換性維持（未使用）


class ChatResponse(BaseModel):
    reply: str
    persona: Dict[str, Any]
