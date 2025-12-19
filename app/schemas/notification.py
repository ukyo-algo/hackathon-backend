# hackathon-backend/app/schemas/notification.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class NotificationResponse(BaseModel):
    """通知レスポンス"""
    id: int
    type: str
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """通知一覧レスポンス"""
    notifications: List[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    """未読通知数レスポンス"""
    unread_count: int
