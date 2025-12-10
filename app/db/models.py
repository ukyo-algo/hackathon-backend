from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Table,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

# --- 中間テーブル: ユーザーがどのキャラを持っているか (Many-to-Many) ---
user_persona_association = Table(
    "user_persona_association",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("persona_id", Integer, ForeignKey("agent_personas.id")),
    Column("obtained_at", DateTime(timezone=True), server_default=func.now()),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_uid = Column(String, unique=True, index=True)
    username = Column(String)
    email = Column(String)
    icon_url = Column(String, nullable=True)

    # ガチャ用のポイント（将来用）
    points = Column(Integer, default=1000)

    # ★追加: 現在セットしているペルソナID
    current_persona_id = Column(Integer, ForeignKey("agent_personas.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # リレーション
    items = relationship("Item", back_populates="seller")
    transactions = relationship("Transaction", back_populates="buyer")
    likes = relationship("Like", back_populates="user")
    comments = relationship("Comment", back_populates="user")

    # ★追加: 現在のパートナーキャラ（1体）
    current_persona = relationship("AgentPersona", foreign_keys=[current_persona_id])

    # ★追加: 所持している全キャラ（リスト）
    owned_personas = relationship(
        "AgentPersona", secondary=user_persona_association, back_populates="owners"
    )


class AgentPersona(Base):
    """
    AIキャラクターの定義テーブル
    """

    __tablename__ = "agent_personas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)  # キャラ名 (例: "熱血勇者")
    description = Column(String)  # 説明文 (一覧画面用)
    system_prompt = Column(Text)  # Geminiへの命令文
    avatar_url = Column(String)  # アイコン画像のURL

    # ガチャのレアリティ（1:Normal, 2:Rare, 3:SSR など）
    rarity = Column(Integer, default=1)

    # リレーション
    owners = relationship(
        "User", secondary=user_persona_association, back_populates="owned_personas"
    )
