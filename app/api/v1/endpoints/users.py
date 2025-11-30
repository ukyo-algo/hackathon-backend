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
from app.schemas import user as user_schema  # ← user_schemaのインポートを復活

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


# ★★★ 一時的なダミー認証ユーザー取得関数 ★★★
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
