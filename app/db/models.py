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
)
from sqlalchemy.orm import relationship
from .database import Base


# ユーザーモデル
class User(Base):
    __tablename__ = "users"

    firebase_uid = Column(String(255), primary_key=True)
    username = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    icon_url = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    items = relationship("Item", back_populates="seller")


# アイテムモデル
# アイテムモデル
class Item(Base):
    __tablename__ = "items"

    item_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    status = Column(String(50), default="on_sale", nullable=False, index=True)
    image_url = Column(String(255), nullable=True)
    is_instant_buy_ok = Column(Boolean, default=True)
    category = Column(String(100), nullable=False)  # カテゴリ
    brand = Column(String(100), nullable=True)  # ブランド名
    condition = Column(String(50), nullable=False)  # 商品の状態
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    seller_id = Column(String(255), ForeignKey("users.firebase_uid"), nullable=False)
    seller = relationship("User", back_populates="items")
