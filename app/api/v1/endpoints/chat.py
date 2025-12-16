# hackathon-backend/app/api/v1/endpoints/chat.py
"""
チャットエンドポイント
LLMキャラとの会話（ページコンテキスト対応）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.db.database import get_db
from app.api.v1.endpoints.users import get_current_user
from app.db import models
from app.services.llm_service import LLMService
from app.schemas.context import PageContext, build_context_text

router = APIRouter()


class ChatRequest(BaseModel):
    """チャットリクエスト"""
    message: str
    page_context: Optional[Dict[str, Any]] = None  # ページコンテキスト
    history: Optional[List[Dict[str, Any]]] = None  # 互換性維持（未使用）


class ChatResponse(BaseModel):
    """チャットレスポンス"""
    reply: str
    persona: Dict[str, Any]


@router.post("", response_model=ChatResponse)
def chat_with_agent(
    chat_in: ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    設定中のLLMキャラと会話する
    
    - message: ユーザーのメッセージ
    - page_context: 現在のページ情報（オプション）
    """
    service = LLMService(db)
    
    # ページコンテキストがあればテキスト化
    context_text = ""
    if chat_in.page_context:
        try:
            page_context = PageContext(**chat_in.page_context)
            context_text = build_context_text(page_context)
        except Exception as e:
            print(f"[chat] page_context parse error: {e}")
    
    # メッセージにコンテキストを付加
    if context_text:
        enhanced_message = f"""
[現在のページ状況]
{context_text}

[ユーザーの質問]
{chat_in.message}
"""
    else:
        enhanced_message = chat_in.message
    
    # LLMに問い合わせ
    result = service.chat_with_persona(
        current_user.firebase_uid,
        current_chat=enhanced_message,
        history=None,  # LLMService側で履歴を一元管理
    )

    return result
