# hackathon-backend/app/api/v1/endpoints/notification.py
"""
通知API: 未読通知の取得、既読処理
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_db
from app.db import models
from app.api.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


# --- Schemas ---

class NotificationResponse(BaseModel):
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
    notifications: List[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


# --- Endpoints ---

@router.get("", response_model=NotificationListResponse, summary="通知一覧取得")
def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    include_read: bool = Query(False, description="既読も含めるか"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """通知一覧を取得（デフォルトは未読のみ）"""
    query = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    )
    
    if not include_read:
        query = query.filter(models.Notification.is_read == False)
    
    notifications = query.order_by(
        models.Notification.created_at.desc()
    ).limit(limit).all()
    
    unread_count = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).count()
    
    return NotificationListResponse(
        notifications=notifications,
        unread_count=unread_count
    )


@router.get("/count", response_model=UnreadCountResponse, summary="未読通知数取得")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """未読通知数を取得"""
    count = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).count()
    
    return UnreadCountResponse(unread_count=count)


@router.post("/{notification_id}/read", summary="通知を既読にする")
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """指定した通知を既読にする"""
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    notification.is_read = True
    db.commit()
    
    return {"message": "Marked as read", "id": notification_id}


@router.post("/read-all", summary="全通知を既読にする")
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """全ての未読通知を既読にする"""
    updated = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    
    db.commit()
    
    return {"message": "All notifications marked as read", "count": updated}
