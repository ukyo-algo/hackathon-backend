# hackathon-backend/app/api/v1/endpoints/users.py

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Header,  # ↓↓↓ 追加: ヘッダーを取得するために必要
)
from sqlalchemy.orm import Session  # Sessionは必須

from app.db.database import get_db
from app.db import models
from app.schemas import user as user_schema

from typing import List
from sqlalchemy.orm import joinedload
from app.schemas import item as item_schema
from app.schemas import transaction as transaction_schema

router = APIRouter()


@router.post("/", response_model=user_schema.UserBase)
def create_user(user: user_schema.UserCreate, db: Session = Depends(get_db)):
    """
    新規ユーザーをデータベースに登録します。すでに存在する場合は既存のユーザー情報を返します。
    """
    # すでに登録済みかチェック
    db_user = (
        db.query(models.User)
        .filter(models.User.firebase_uid == user.firebase_uid)
        .first()
    )
    if db_user:  # すでに存在する場合はそのまま返す
        return db_user

    new_user = models.User(
        firebase_uid=user.firebase_uid,
        username=user.username,
        email=user.email,
        icon_url=user.icon_url,
    )  # 新しいユーザーを作成
    db.add(new_user)  # 新しいユーザーをDBセッションに追加
    db.commit()  # DBに保存
    db.refresh(new_user)  # 新しいユーザーの情報をDBから取得して更新
    return new_user


def get_current_user(
    db: Session = Depends(get_db),
    # フロントエンドから "X-Firebase-Uid" というヘッダーでUIDを受け取る
    x_firebase_uid: str | None = Header(default=None),
):
    """
    リクエストヘッダーのUIDを元に、現在のユーザーを特定する。
    """
    if x_firebase_uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報(X-Firebase-Uid)が不足しています",
        )

    # DBからユーザーを検索
    user = (
        db.query(models.User).filter(models.User.firebase_uid == x_firebase_uid).first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません。先に登録してください。",
        )
    return user


@router.get("/me/items", response_model=List[item_schema.Item])
def read_own_items(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が「出品」した商品の一覧を取得
    """
    items = (
        db.query(models.Item)
        .options(joinedload(models.Item.seller))  # N+1対策
        .filter(models.Item.seller_id == current_user.firebase_uid)
        .order_by(models.Item.created_at.desc())
        .all()
    )
    return items


@router.get("/me/transactions", response_model=List[transaction_schema.Transaction])
def read_own_transactions(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が「購入」した履歴を取得（商品情報付き）
    """
    transactions = (
        db.query(models.Transaction)
        .options(joinedload(models.Transaction.item))  # 商品情報も一緒に取得
        .filter(models.Transaction.buyer_id == current_user.firebase_uid)
        .order_by(models.Transaction.created_at.desc())
        .all()
    )
    return transactions


@router.get("/me/likes", response_model=List[item_schema.Item])
def read_own_likes(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が「いいね」した商品の一覧を取得
    """
    liked_items = (
        db.query(models.Item)
        .join(models.Like, models.Item.item_id == models.Like.item_id)
        .options(joinedload(models.Item.seller))  # N+1対策
        .filter(models.Like.user_id == current_user.firebase_uid)
        .order_by(models.Like.created_at.desc())
        .all()
    )
    return liked_items


@router.get("/me/comments", response_model=List[item_schema.Item])
def read_own_commented_items(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が「コメント」した商品の一覧を取得
    """
    commented_items = (
        db.query(models.Item)
        .join(models.Comment, models.Item.item_id == models.Comment.item_id)
        .options(joinedload(models.Item.seller))  # N+1対策
        .filter(models.Comment.user_id == current_user.firebase_uid)
        .order_by(models.Comment.created_at.desc())
        .all()
    )
    return commented_items
