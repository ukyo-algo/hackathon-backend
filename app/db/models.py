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

    # ゲーム内通貨（ガチャポイント）: ガチャ・購入報酬すべてこれで管理
    gacha_points = Column(Integer, default=1000)  # 旧名: coins
    
    # 記憶のかけら: レベルアップに使用
    memory_fragments = Column(Integer, default=0)
    
    # デイリーパートナー: 0時時点で装備していたペルソナ（グリッチ対策）
    daily_partner_persona_id = Column(Integer, ForeignKey("agent_personas.id"), nullable=True)
    daily_partner_set_at = Column(DateTime(timezone=True), nullable=True)
    
    # クエスト: 最後にレコメンドクエストを完了した時刻
    last_recommend_quest_at = Column(DateTime(timezone=True), nullable=True)
    
    # ミッション: ログインボーナス関連
    last_login_bonus_at = Column(DateTime(timezone=True), nullable=True)  # 最後にログインボーナスを受け取った時刻
    login_streak = Column(Integer, default=0)  # 連続ログイン日数
    total_login_days = Column(Integer, default=0)  # 累計ログイン日数
    last_weekly_likes_at = Column(DateTime(timezone=True), nullable=True)  # 週間いいねボーナス受取時刻

    # 現在セットしているペルソナID
    current_persona_id = Column(Integer, ForeignKey("agent_personas.id"), nullable=True)
    
    # サブペルソナID（月額パス加入者のみ使用可能）
    sub_persona_id = Column(Integer, ForeignKey("agent_personas.id"), nullable=True)
    
    # サブスクリプション: free/monthly
    subscription_tier = Column(String(50), default="free")
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # リレーション
    items = relationship("Item", back_populates="seller")
    transactions = relationship("Transaction", back_populates="buyer")
    likes = relationship("Like", back_populates="user")
    comments = relationship("Comment", back_populates="user")

    # キャラクター関連
    current_persona = relationship("AgentPersona", foreign_keys=[current_persona_id])
    sub_persona = relationship("AgentPersona", foreign_keys=[sub_persona_id])

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
    # 進行ステータス（最小3種）
    status = Column(String(32), default="pending_shipment")
    shipped_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

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
    rarity_name = Column(String(50), default="ノーマル")
    skill_name = Column(String(255))
    skill_effect = Column(String(255))

    # キャラクターのテーマカラー
    theme_color = Column(String(50), default="#1976d2")
    
    # キャラクター詳細情報 (追加)
    origin = Column(Text, nullable=True)
    tragedy = Column(Text, nullable=True)
    obsession = Column(Text, nullable=True)
    mbti = Column(String(50), nullable=True)

    pass


# --- 7. ChatMessage Model (ユーザー別チャット履歴) ---
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    # 多くの既存FKと整合させるため firebase_uid を参照
    user_id = Column(String(255), ForeignKey("users.firebase_uid"), index=True)
    role = Column(String(16))  # 'user' | 'ai' | 'system'
    type = Column(String(50), nullable=True)  # 'chat' | 'guidance' | None
    content = Column(Text)
    persona_id = Column(Integer, ForeignKey("agent_personas.id"), nullable=True)
    page_path = Column(String(255), nullable=True)  # どのページで発言されたか
    is_visible = Column(Boolean, default=True)  # UIに表示するかどうか
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # リレーション
    user = relationship("User", back_populates="chat_messages")
    persona = relationship("AgentPersona")


# User へ逆参照を追加
User.chat_messages = relationship("ChatMessage", back_populates="user")


# --- 8. RewardEvent Model (コイン入手台帳) ---
class RewardEvent(Base):
    __tablename__ = "reward_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), ForeignKey("users.firebase_uid"), index=True)
    kind = Column(String(64), index=True)  # 'hourly_claim' など、入手種別
    amount = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # リレーション
    user = relationship("User", back_populates="reward_events")


# User へ逆参照を追加
User.reward_events = relationship("RewardEvent", back_populates="user")


# --- 9. LLMRecommendation Model (おすすめ履歴) ---
class LLMRecommendation(Base):
    __tablename__ = "llm_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), ForeignKey("users.firebase_uid"), index=True)
    item_id = Column(String(255), ForeignKey("items.item_id"), index=True)
    reason = Column(Text, nullable=True)  # AIが生成した推薦理由
    persona_name = Column(String(255), nullable=True)  # おすすめを生成したペルソナ名
    persona_avatar_url = Column(String(512), nullable=True)  # ペルソナのアバター画像URL
    interest = Column(String(16), nullable=True)  # null / interested / not_interested
    recommended_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # リレーション
    user = relationship("User", back_populates="recommendations")
    item = relationship("Item")


# User へ逆参照を追加
User.recommendations = relationship("LLMRecommendation", back_populates="user")


# --- 10. UserCoupon Model (クーポン) ---
class UserCoupon(Base):
    __tablename__ = "user_coupons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    # クーポンタイプ: "shipping_discount", "gacha_discount"
    coupon_type = Column(String(50))
    
    # 割引率（%）
    discount_percent = Column(Integer)
    
    # 有効期限
    expires_at = Column(DateTime(timezone=True))
    
    # 使用日時（nullなら未使用）
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # どのペルソナから発行されたか
    issued_by_persona_id = Column(Integer, ForeignKey("agent_personas.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    user = relationship("User", back_populates="coupons")
    issued_by_persona = relationship("AgentPersona")


# User へ逆参照を追加
User.coupons = relationship("UserCoupon", back_populates="user")


# --- 11. UserMission Model (ワンタイムミッション管理) ---
class UserMission(Base):
    __tablename__ = "user_missions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    # ミッションキー: "first_listing", "first_purchase", "login_streak_3" など
    mission_key = Column(String(50), index=True)
    
    # 達成日時
    completed_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    user = relationship("User", back_populates="missions")


# User へ逆参照を追加
User.missions = relationship("UserMission", back_populates="user")


# --- 12. Notification Model (通知) ---
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)  # 通知を受け取るユーザー
    
    # 通知タイプ: "comment", "purchase", "like" など
    type = Column(String(50), index=True)
    title = Column(String(255))
    message = Column(Text)
    link = Column(String(512))  # クリック時の遷移先
    
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    user = relationship("User", back_populates="notifications")


# User へ逆参照を追加
User.notifications = relationship("Notification", back_populates="user")


# --- 13. Conversation Model (ダイレクトメッセージの会話) ---
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    
    # 会話の参加者（2人）
    user1_id = Column(Integer, ForeignKey("users.id"), index=True)
    user2_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    # 関連商品（オプション：商品に関する問い合わせの場合）
    item_id = Column(String(255), ForeignKey("items.item_id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # リレーション
    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    item = relationship("Item")
    messages = relationship("DirectMessage", back_populates="conversation", order_by="DirectMessage.created_at")


# --- 14. DirectMessage Model (ダイレクトメッセージ) ---
class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    content = Column(Text)
    is_read = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # リレーション
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")
