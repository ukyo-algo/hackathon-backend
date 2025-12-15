# hackathon-backend/app/api/v1/endpoints/chat.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.chat import ChatRequest, ChatResponse

from app.db.database import get_db
from app.api.v1.endpoints.users import get_current_user
from app.db import models
from app.services.llm_service import LLMService

router = APIRouter()


"""Pydanticスキーマはapp/schemas/chat.pyへ移動"""


@router.post("", response_model=ChatResponse)
def chat_with_agent(
    chat_in: ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    設定中のLLMキャラと会話する（チャット履歴を考慮）
    """
    service = LLMService(db)

    # チャット履歴（オプション）をサービス層に渡す
    result = service.chat_with_persona(
        current_user.firebase_uid,
        current_chat=chat_in.message,
        history=None,  # LLMService側で履歴を一元管理
    )

    return result
