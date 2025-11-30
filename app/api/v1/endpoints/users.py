from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.schemas import user as user_schema

router = APIRouter()


@router.post("/", response_model=user_schema.UserBase)
def create_user(user: user_schema.UserCreate, db: Session = Depends(get_db)):
    # すでに登録済みかチェック
    db_user = (
        db.query(models.User)
        .filter(models.User.firebase_uid == user.firebase_uid)
        .first()
    )
    if db_user:
        return db_user

    new_user = models.User(
        firebase_uid=user.firebase_uid,
        username=user.username,
        email=user.email,
        icon_url=user.icon_url,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
