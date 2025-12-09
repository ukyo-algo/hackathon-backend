# hackathon-backend/app/db/models.py

import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,
    Boolean,
    TIMESTAMP,
    ForeignKey,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .database import Base


# ユーザーモデル
class User(Base):
    __tablename__ = "users"

    firebase_uid = Column(String(255), primary_key=True)
    username = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    icon_url = Column(Text, nullable=True)

    # ★ LLM機能追加項目
    points = Column(Integer, default=0, nullable=False)

    # 1. まず ForeignKey のカラムを定義する (NameError回避のためrelationshipより上に配置)
    current_persona_id = Column(Integer, ForeignKey("agent_personas.id"), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # リレーションシップ
    items = relationship("Item", back_populates="seller")
    likes = relationship("Like", back_populates="user")
    comments = relationship("Comment", back_populates="user")

    # 2. 定義済みのカラム名を使ってリレーションシップを定義する
    current_persona = relationship(
        "AgentPersona", foreign_keys=[current_persona_id], viewonly=True
    )

    # 所持キャラクター一覧
    owned_personas = relationship("UserPersona", back_populates="user")


# 商品モデル
class Item(Base):
    __tablename__ = "items"
    item_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    status = Column(String(50), default="on_sale", nullable=False, index=True)
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


# いいねモデル
class Like(Base):
    __tablename__ = "likes"
    user_id = Column(String(255), ForeignKey("users.firebase_uid"), primary_key=True)
    item_id = Column(String(36), ForeignKey("items.item_id"), primary_key=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    user = relationship("User", back_populates="likes")
    item = relationship("Item", back_populates="likes")


# コメントモデル
class Comment(Base):
    __tablename__ = "comments"
    comment_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String(36), ForeignKey("items.item_id"), nullable=False)
    user_id = Column(String(255), ForeignKey("users.firebase_uid"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    item = relationship("Item", back_populates="comments")
    user = relationship("User", back_populates="comments")


# ★新規追加: AIキャラクター（ペルソナ）定義
class AgentPersona(Base):
    __tablename__ = "agent_personas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # 性格を決めるシステムプロンプト
    system_prompt = Column(Text, nullable=False)

    # アバター画像URL
    avatar_url = Column(Text, nullable=True)

    # 背景テーマ（MUIの色設定やクラス名に使う予定）
    background_theme = Column(String(100), nullable=True)

    rarity = Column(Integer, default=1, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


# ★新規追加: ユーザーの所持キャラ（好感度を管理）
class UserPersona(Base):
    __tablename__ = "user_personas"

    user_id = Column(String(255), ForeignKey("users.firebase_uid"), primary_key=True)
    persona_id = Column(Integer, ForeignKey("agent_personas.id"), primary_key=True)

    favorability = Column(Integer, default=0, nullable=False)  # 好感度
    obtained_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="owned_personas")
    persona = relationship("AgentPersona")

    __table_args__ = (
        UniqueConstraint("user_id", "persona_id", name="_user_persona_uc"),
    )
