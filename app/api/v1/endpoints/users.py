from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)  # ← HTTPExceptionとstatusを追加
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.schemas import user as user_schema

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
# 商品出品機能などで認証済みユーザーが必要なため、一時的に固定ユーザーを返す
def get_current_user_dummy(db: Session = Depends(get_db)):
    """
    ダミーの認証ユーザーを取得する。seed_user_1を固定で返す。
    本来はリクエストヘッダーのFirebase IDトークンを検証する。
    """
    # 開発環境のダミーユーザーID (seed.py で定義されたもの)
    DUMMY_UID = "seed_user_1_uid"
    user = db.query(models.User).filter(models.User.firebase_uid == DUMMY_UID).first()
    if user is None:
        # seed.pyが実行されていない場合に備えてエラーを出す
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dummy user not found. Please run seed.py",
        )
    return user
