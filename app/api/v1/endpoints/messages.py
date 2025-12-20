# app/api/v1/endpoints/messages.py
"""
ダイレクトメッセージ機能のAPIエンドポイント
- REST: 会話一覧、メッセージ履歴、既読更新
- WebSocket: リアルタイムメッセージ配信
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc, func
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime
import json

from app.db.database import get_db
from app.db import models
from app.api.v1.endpoints.users import get_current_user

router = APIRouter()


# --- Pydantic Schemas ---
class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: int
    sender_id: int
    sender_username: str
    sender_icon_url: Optional[str]
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationPreview(BaseModel):
    id: int
    other_user_id: int
    other_user_username: str
    other_user_icon_url: Optional[str]
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    unread_count: int
    item_id: Optional[str]
    item_name: Optional[str]

    class Config:
        from_attributes = True


# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        # user_id -> WebSocket connection
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception:
                self.disconnect(user_id)


manager = ConnectionManager()


# --- REST Endpoints ---

@router.get("/conversations", response_model=List[ConversationPreview])
def get_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    現在のユーザーの会話一覧を取得（最終メッセージの新しい順）
    """
    # ユーザーが参加している会話を取得
    conversations = (
        db.query(models.Conversation)
        .options(
            joinedload(models.Conversation.user1),
            joinedload(models.Conversation.user2),
            joinedload(models.Conversation.item),
        )
        .filter(
            or_(
                models.Conversation.user1_id == current_user.id,
                models.Conversation.user2_id == current_user.id,
            )
        )
        .order_by(desc(models.Conversation.updated_at))
        .all()
    )

    result = []
    for conv in conversations:
        # 相手ユーザーを特定
        other_user = conv.user2 if conv.user1_id == current_user.id else conv.user1

        # 最後のメッセージを取得
        last_msg = (
            db.query(models.DirectMessage)
            .filter(models.DirectMessage.conversation_id == conv.id)
            .order_by(desc(models.DirectMessage.created_at))
            .first()
        )

        # 未読メッセージ数をカウント
        unread_count = (
            db.query(func.count(models.DirectMessage.id))
            .filter(
                models.DirectMessage.conversation_id == conv.id,
                models.DirectMessage.sender_id != current_user.id,
                models.DirectMessage.is_read == False,
            )
            .scalar()
        )

        result.append(ConversationPreview(
            id=conv.id,
            other_user_id=other_user.id,
            other_user_username=other_user.username or "ユーザー",
            other_user_icon_url=other_user.icon_url,
            last_message=last_msg.content[:50] if last_msg else None,
            last_message_at=last_msg.created_at if last_msg else conv.created_at,
            unread_count=unread_count,
            item_id=conv.item_id,
            item_name=conv.item.name if conv.item else None,
        ))

    return result


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(
    conversation_id: int,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    会話のメッセージ履歴を取得
    """
    # 会話の存在確認とアクセス権チェック
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="会話が見つかりません")

    if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
        raise HTTPException(status_code=403, detail="この会話にアクセスする権限がありません")

    messages = (
        db.query(models.DirectMessage)
        .options(joinedload(models.DirectMessage.sender))
        .filter(models.DirectMessage.conversation_id == conversation_id)
        .order_by(models.DirectMessage.created_at)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        MessageResponse(
            id=msg.id,
            sender_id=msg.sender_id,
            sender_username=msg.sender.username or "ユーザー",
            sender_icon_url=msg.sender.icon_url,
            content=msg.content,
            is_read=msg.is_read,
            created_at=msg.created_at,
        )
        for msg in messages
    ]


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: int,
    message: MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    メッセージを送信（REST API経由）
    """
    # 会話の存在確認とアクセス権チェック
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="会話が見つかりません")

    if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
        raise HTTPException(status_code=403, detail="この会話にアクセスする権限がありません")

    # メッセージを作成
    new_message = models.DirectMessage(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=message.content,
    )
    db.add(new_message)
    
    # 会話の更新日時を更新
    conversation.updated_at = datetime.now()
    
    db.commit()
    db.refresh(new_message)

    # 相手ユーザーを特定
    other_user_id = conversation.user2_id if conversation.user1_id == current_user.id else conversation.user1_id

    # WebSocket経由でリアルタイム配信
    message_data = {
        "type": "new_message",
        "conversation_id": conversation_id,
        "message": {
            "id": new_message.id,
            "sender_id": current_user.id,
            "sender_username": current_user.username or "ユーザー",
            "sender_icon_url": current_user.icon_url,
            "content": new_message.content,
            "is_read": False,
            "created_at": new_message.created_at.isoformat(),
        }
    }
    await manager.send_personal_message(message_data, other_user_id)

    # 通知を作成
    notification = models.Notification(
        user_id=other_user_id,
        type="message",
        title="新しいメッセージ",
        message=f"{current_user.username or 'ユーザー'}からメッセージが届きました",
        link=f"/messages/{conversation_id}",
    )
    db.add(notification)
    db.commit()

    return MessageResponse(
        id=new_message.id,
        sender_id=current_user.id,
        sender_username=current_user.username or "ユーザー",
        sender_icon_url=current_user.icon_url,
        content=new_message.content,
        is_read=False,
        created_at=new_message.created_at,
    )


@router.post("/conversations/{conversation_id}/read")
def mark_as_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    会話内の未読メッセージを既読にする
    """
    # 会話の存在確認とアクセス権チェック
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="会話が見つかりません")

    if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
        raise HTTPException(status_code=403, detail="この会話にアクセスする権限がありません")

    # 相手からのメッセージを既読に
    updated = (
        db.query(models.DirectMessage)
        .filter(
            models.DirectMessage.conversation_id == conversation_id,
            models.DirectMessage.sender_id != current_user.id,
            models.DirectMessage.is_read == False,
        )
        .update({"is_read": True})
    )
    db.commit()

    # 相手にWebSocketで既読通知
    other_user_id = conversation.user2_id if conversation.user1_id == current_user.id else conversation.user1_id
    # 非同期なので別途処理が必要だが、ここでは簡略化

    return {"marked_as_read": updated}


@router.post("/conversations/start")
def start_conversation(
    other_user_id: int = Query(..., description="相手ユーザーID"),
    item_id: Optional[str] = Query(None, description="関連商品ID（オプション）"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    新しい会話を開始（または既存の会話を取得）
    """
    if other_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="自分自身とは会話できません")

    # 既存の会話を検索
    existing = (
        db.query(models.Conversation)
        .filter(
            or_(
                and_(
                    models.Conversation.user1_id == current_user.id,
                    models.Conversation.user2_id == other_user_id,
                ),
                and_(
                    models.Conversation.user1_id == other_user_id,
                    models.Conversation.user2_id == current_user.id,
                ),
            )
        )
        .first()
    )

    if existing:
        return {"conversation_id": existing.id, "is_new": False}

    # 相手ユーザーの存在確認
    other_user = db.query(models.User).filter(models.User.id == other_user_id).first()
    if not other_user:
        raise HTTPException(status_code=404, detail="相手ユーザーが見つかりません")

    # 新しい会話を作成
    conversation = models.Conversation(
        user1_id=current_user.id,
        user2_id=other_user_id,
        item_id=item_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return {"conversation_id": conversation.id, "is_new": True}


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    未読メッセージの総数を取得
    """
    count = (
        db.query(func.count(models.DirectMessage.id))
        .join(models.Conversation)
        .filter(
            or_(
                models.Conversation.user1_id == current_user.id,
                models.Conversation.user2_id == current_user.id,
            ),
            models.DirectMessage.sender_id != current_user.id,
            models.DirectMessage.is_read == False,
        )
        .scalar()
    )
    return {"unread_count": count}


@router.get("/conversations/{conversation_id}/relationship")
def get_relationship_info(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    DM相手との関係情報（取引・いいね・コメント）を取得
    AI返信アシスト用のコンテキスト
    """
    # 会話の存在確認
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="会話が見つかりません")

    if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
        raise HTTPException(status_code=403, detail="この会話にアクセスする権限がありません")

    # 相手ユーザー
    other_user_id = conversation.user2_id if conversation.user1_id == current_user.id else conversation.user1_id
    other_user = db.query(models.User).filter(models.User.id == other_user_id).first()
    
    if not other_user:
        return {"relationship": None}

    # 1. 取引情報: 相手から購入した商品、相手に売った商品
    # 相手の出品した商品を自分が購入
    purchased_from_other = (
        db.query(models.Transaction)
        .join(models.Item, models.Transaction.item_id == models.Item.item_id)
        .filter(
            models.Transaction.buyer_id == current_user.firebase_uid,
            models.Item.seller_id == other_user.firebase_uid,
        )
        .all()
    )
    
    # 自分の出品した商品を相手が購入
    sold_to_other = (
        db.query(models.Transaction)
        .join(models.Item, models.Transaction.item_id == models.Item.item_id)
        .filter(
            models.Transaction.buyer_id == other_user.firebase_uid,
            models.Item.seller_id == current_user.firebase_uid,
        )
        .all()
    )

    # 2. いいね情報: 相手の商品への自分のいいね、自分の商品への相手のいいね
    my_likes_on_other = (
        db.query(models.Like)
        .join(models.Item, models.Like.item_id == models.Item.item_id)
        .filter(
            models.Like.user_id == current_user.firebase_uid,
            models.Item.seller_id == other_user.firebase_uid,
        )
        .count()
    )
    
    other_likes_on_mine = (
        db.query(models.Like)
        .join(models.Item, models.Like.item_id == models.Item.item_id)
        .filter(
            models.Like.user_id == other_user.firebase_uid,
            models.Item.seller_id == current_user.firebase_uid,
        )
        .count()
    )

    # 3. コメント情報: 相手の商品への自分のコメント、自分の商品への相手のコメント
    my_comments_on_other = (
        db.query(models.Comment)
        .join(models.Item, models.Comment.item_id == models.Item.item_id)
        .filter(
            models.Comment.user_id == current_user.firebase_uid,
            models.Item.seller_id == other_user.firebase_uid,
        )
        .all()
    )
    
    other_comments_on_mine = (
        db.query(models.Comment)
        .join(models.Item, models.Comment.item_id == models.Item.item_id)
        .filter(
            models.Comment.user_id == other_user.firebase_uid,
            models.Item.seller_id == current_user.firebase_uid,
        )
        .all()
    )

    return {
        "relationship": {
            "purchases": {
                "from_other": [
                    {"item_name": t.item.name if t.item else "不明", "price": t.price, "status": t.status}
                    for t in purchased_from_other
                ],
                "to_other": [
                    {"item_name": t.item.name if t.item else "不明", "price": t.price, "status": t.status}
                    for t in sold_to_other
                ],
            },
            "likes": {
                "i_liked_their_items": my_likes_on_other,
                "they_liked_my_items": other_likes_on_mine,
            },
            "comments": {
                "i_commented_on_their_items": [
                    {"item_name": c.item.name if c.item else "不明", "content": c.content[:50]}
                    for c in my_comments_on_other[-5:]  # 直近5件
                ],
                "they_commented_on_my_items": [
                    {"item_name": c.item.name if c.item else "不明", "content": c.content[:50]}
                    for c in other_comments_on_mine[-5:]  # 直近5件
                ],
            },
            "conversation_item": conversation.item.name if conversation.item else None,
        }
    }


# --- WebSocket Endpoint ---

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    WebSocket接続エンドポイント
    リアルタイムでメッセージを受信する
    """
    await manager.connect(websocket, user_id)
    try:
        while True:
            # クライアントからのメッセージを待機（keepalive用）
            data = await websocket.receive_text()
            # pingを受け取ったらpongを返す
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(user_id)
