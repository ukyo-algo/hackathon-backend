import uuid
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


# --- 中間テーブル改め、所持状況管理モデル ---
class UserPersona(Base):
    __tablename__ = "user_personas"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    persona_id = Column(Integer, ForeignKey("agent_personas.id"), primary_key=True)

    # 重複入手数（クラロワ方式）
    stack_count = Column(Integer, default=1)
    # レベル（将来用）
    level = Column(Integer, default=1)
    # 経験値（将来用）
    exp = Column(Integer, default=0)

    obtained_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    user = relationship("User", back_populates="owned_personas_association")
    persona = relationship("AgentPersona")


# --- 1. User Model ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # MySQLではStringに長さ指定が必須 (特にindex/uniqueをつける場合)
    firebase_uid = Column(String(255), unique=True, index=True)
    username = Column(String(255))
    email = Column(String(255))
    icon_url = Column(String(512), nullable=True)  # URLは長めにとる

    # ガチャ用のポイント
    points = Column(Integer, default=1000)

    # 現在セットしているペルソナID
    current_persona_id = Column(Integer, ForeignKey("agent_personas.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # リレーション
    items = relationship("Item", back_populates="seller")
    transactions = relationship("Transaction", back_populates="buyer")
    likes = relationship("Like", back_populates="user")
    comments = relationship("Comment", back_populates="user")

    # キャラクター関連
    current_persona = relationship("AgentPersona", foreign_keys=[current_persona_id])

    # 中間テーブルへのリレーション
    owned_personas_association = relationship("UserPersona", back_populates="user")

    # 便利なショートカット（直接Personaオブジェクトにアクセスしたい場合用）
    # ※ association_proxy を使うとよりスマートですが、今回はプロパティで簡易実装するか、
    #   ロジック側で owned_personas_association を経由するように修正します。


# --- 2. Item Model ---
class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    # UUIDなどを入れる場合も長さを指定
    item_id = Column(
        String(255), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    name = Column(String(255))
    description = Column(Text)  # Text型は長さ指定不要
    price = Column(Integer)
    category = Column(String(255))
    brand = Column(String(255), nullable=True)
    condition = Column(String(255))
    image_url = Column(String(512), nullable=True)

    # ステータス: 'on_sale' (出品中), 'sold' (売り切れ)
    status = Column(String(50), default="on_sale")
    is_instant_buy_ok = Column(Boolean, default=True)

    # 外部キーの型も参照先(User.firebase_uid)と合わせる
    seller_id = Column(String(255), ForeignKey("users.firebase_uid"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # リレーション
    seller = relationship("User", back_populates="items")
    transaction = relationship("Transaction", back_populates="item", uselist=False)
    likes = relationship("Like", back_populates="item")
    comments = relationship("Comment", back_populates="item")

    @property
    def like_count(self) -> int:
        """この商品に付いたいいねの数を返す"""
        return len(self.likes)

    @property
    def comments_count(self):
        """この商品に付いたコメントの数を返す"""
        return len(self.comments)


# --- 3. Transaction Model (取引) ---
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(
        String(255), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    item_id = Column(String(255), ForeignKey("items.item_id"))
    buyer_id = Column(String(255), ForeignKey("users.firebase_uid"))
    price = Column(Integer)  # 取引成立時の価格

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    item = relationship("Item", back_populates="transaction")
    buyer = relationship("User", back_populates="transactions")


# --- 4. Like Model (いいね) ---
class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), ForeignKey("users.firebase_uid"))
    item_id = Column(String(255), ForeignKey("items.item_id"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    user = relationship("User", back_populates="likes")
    item = relationship("Item", back_populates="likes")


# --- 5. Comment Model (コメント) ---
class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(
        String(255), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    user_id = Column(String(255), ForeignKey("users.firebase_uid"))
    item_id = Column(String(255), ForeignKey("items.item_id"))
    content = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    user = relationship("User", back_populates="comments")
    item = relationship("Item", back_populates="comments")


# --- 6. AgentPersona Model (AIキャラ) ---
class AgentPersona(Base):
    __tablename__ = "agent_personas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True)
    description = Column(String(255))
    system_prompt = Column(Text)
    avatar_url = Column(String(512))
    rarity = Column(Integer, default=1)
    skill_name = Column(String(255))
    skill_effect = Column(String(255))

    # キャラクターのテーマカラー
    theme_color = Column(String(50), default="#1976d2")

    # リレーション
    # owners = relationship("User", secondary="user_personas", back_populates="owned_personas")
    # ↑ 中間テーブルをクラス化したため、直接のMany-to-Manyリレーションは定義しづらい
    # 必要なら association_proxy を使うが、今回は逆参照はあまり使わないのでコメントアウトか削除
    pass
