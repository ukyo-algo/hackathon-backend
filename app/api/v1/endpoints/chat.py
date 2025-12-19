# hackathon-backend/app/api/v1/endpoints/chat.py
"""
チャットエンドポイント
LLMキャラとの会話（ページコンテキスト対応）+ 履歴保存
"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from typing import Optional, List

from app.db.database import get_db
from app.api.v1.endpoints.users import get_current_user
from app.db import models
from app.services.llm_service import LLMService
from app.schemas.context import PageContext, build_context_text
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ImageAnalysisRequest,
    ImageAnalysisResponse,
)

router = APIRouter()


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


# --- チャット履歴保存・取得 ---

@router.post("/messages", response_model=ChatMessageResponse)
def save_message(
    message: ChatMessageCreate,
    db: Session = Depends(get_db),
    x_firebase_uid: str = Header(...),
):
    """
    チャットメッセージを保存する
    """
    # ユーザーの現在のペルソナを取得
    user = db.query(models.User).filter(
        models.User.firebase_uid == x_firebase_uid
    ).first()
    
    persona_id = user.current_persona_id if user else None
    persona_name = user.current_persona.name if user and user.current_persona else None

    # メッセージを保存
    db_message = models.ChatMessage(
        user_id=x_firebase_uid,
        role=message.role,
        content=message.content,
        type=message.type,
        persona_id=persona_id,
        page_path=message.page_path,
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)

    return ChatMessageResponse(
        id=db_message.id,
        role=db_message.role,
        content=db_message.content,
        type=db_message.type,
        page_path=db_message.page_path,
        persona_name=persona_name,
        created_at=db_message.created_at.isoformat() if db_message.created_at else "",
    )


@router.get("/messages", response_model=List[ChatMessageResponse])
def get_messages(
    limit: int = 10,
    db: Session = Depends(get_db),
    x_firebase_uid: str = Header(...),
):
    """
    直近のチャット履歴を取得する（最新のものが最後）
    """
    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.user_id == x_firebase_uid)
        .filter(models.ChatMessage.is_visible == True)  # 表示可能なメッセージのみ
        .order_by(models.ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    
    # 古い順に並び替え
    messages = list(reversed(messages))

    result = []
    for msg in messages:
        persona_name = None
        if msg.persona:
            persona_name = msg.persona.name
        
        result.append(ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            type=msg.type,
            page_path=msg.page_path,
            persona_name=persona_name,
            created_at=msg.created_at.isoformat() if msg.created_at else "",
        ))
    
    return result


# --- 画像解析出品サポート ---

@router.post("/analyze-image", response_model=ImageAnalysisResponse)
def analyze_listing_image(
    req: ImageAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    出品用の画像を解析して商品情報を推定する
    
    - image_base64: Base64エンコードされた画像データ
    - prompt: 追加の指示（例: 「これを出品したい」）
    """
    service = LLMService(db)
    
    result = service.analyze_image_for_listing(
        user_id=current_user.firebase_uid,
        image_base64=req.image_base64,
        prompt=req.prompt,
    )
    
    return result
