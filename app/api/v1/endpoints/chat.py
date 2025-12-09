# hackathon-backend/app/api/v1/endpoints/chat.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.api.v1.endpoints.users import get_current_user
from app.db import models
from app.services.llm_service import LLMService

router = APIRouter()


# リクエストボディの定義
class ChatRequest(BaseModel):
    message: str


# レスポンスの定義
class ChatResponse(BaseModel):
    reply: str
    persona: dict


@router.post("", response_model=ChatResponse)
def chat_with_agent(
    chat_in: ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    設定中のLLMキャラと会話する
    """
    service = LLMService(db)

    # サービス層に丸投げ（ロジック分離）
    result = service.chat_with_persona(current_user.firebase_uid, chat_in.message)

    return result
