# hackathon-backend/app/db/models.py

import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,  # ← Text型を使用
    Boolean,
    TIMESTAMP,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship
from .database import Base


# ユーザーモデル
class User(Base):
    __tablename__ = "users"

    firebase_uid = Column(String(255), primary_key=True)
    username = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)

    # ↓↓↓ 修正: URLは長いので Text 型にする ↓↓↓
    icon_url = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    items = relationship("Item", back_populates="seller")
    likes = relationship("Like", back_populates="user")
    comments = relationship("Comment", back_populates="user")


# アイテムモデル
class Item(Base):
    __tablename__ = "items"

    item_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    status = Column(String(50), default="on_sale", nullable=False, index=True)

    # ↓↓↓ 修正: URLは長いので Text 型にする ↓↓↓
    image_url = Column(Text, nullable=True)

    is_instant_buy_ok = Column(Boolean, default=True)
    category = Column(String(100), nullable=False)
    brand = Column(String(100), nullable=True)
    condition = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    seller_id = Column(String(255), ForeignKey("users.firebase_uid"), nullable=False)
    seller = relationship("User", back_populates="items")
    likes = relationship("Like", back_populates="item")
    comments = relationship("Comment", back_populates="item")


# 取引モデル
class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    item_id = Column(String(36), ForeignKey("items.item_id"), nullable=False)
    buyer_id = Column(String(255), ForeignKey("users.firebase_uid"), nullable=False)
    price = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    item = relationship("Item")
    buyer = relationship("User")


class Like(Base):
    __tablename__ = "likes"

    user_id = Column(String(255), ForeignKey("users.firebase_uid"), primary_key=True)
    item_id = Column(String(36), ForeignKey("items.item_id"), primary_key=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="likes")
    item = relationship("Item", back_populates="likes")


class Comment(Base):
    __tablename__ = "comments"

    comment_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String(36), ForeignKey("items.item_id"), nullable=False)
    user_id = Column(String(255), ForeignKey("users.firebase_uid"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    item = relationship("Item", back_populates="comments")
    user = relationship("User", back_populates="comments")
