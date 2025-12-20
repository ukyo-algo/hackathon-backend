from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime


class PersonaBase(BaseModel):
    id: int
    name: str
    avatar_url: Optional[str] = None
    description: Optional[str] = None
    theme_color: Optional[str] = "#1976d2"
    rarity: Optional[int] = None
    rarity_name: Optional[str] = None
    # 追加フィールド: キャラクター詳細情報
    origin: Optional[str] = None
    tragedy: Optional[str] = None
    obsession: Optional[str] = None
    mbti: Optional[str] = None
    skill_name: Optional[str] = None
    skill_effect: Optional[str] = None

    class Config:
        from_attributes = True


class SellerInfo(BaseModel):
    """
    商品出品者として返すシンプルなスキーマ
    """
    id: Optional[int] = None  # データベースのユーザーID (DM用)
    firebase_uid: Optional[str] = None
    username: Optional[str] = None
    icon_url: Optional[str] = None
    average_rating: Optional[float] = 0.0
    rating_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    """
    APIでユーザー情報を返すときの基本スキーマ
    """

    id: int  # データベースのユーザーID
    firebase_uid: str
    username: str
    email: EmailStr
    icon_url: str | None = None
    current_persona_id: Optional[int] = None  # Optionalに変更
    current_persona: Optional["PersonaBase"] = None
    # サブペルソナ（月額パス加入者のみ）
    sub_persona_id: Optional[int] = None
    sub_persona: Optional["PersonaBase"] = None
    # サブスクリプション情報
    subscription_tier: str = "free"
    subscription_expires_at: Optional[datetime] = None
    # ポイント
    gacha_points: int = 0
    memory_fragments: int = 0

    # SQLAlchemyモデル（models.User）から
    # Pydanticモデル（UserBase）への自動変換を有効にする
    model_config = ConfigDict(from_attributes=True)


# UserBaseを継承せず、ユーザー作成時に必要なフィールドのみ定義
class UserCreate(BaseModel):
    """
    APIがユーザー作成時にリクエストボディとして受け取るスキーマ
    """
    firebase_uid: str
    username: str
    email: EmailStr
    icon_url: Optional[str] = None
    current_persona_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# --- リクエストスキーマ ---
class AddFragmentsRequest(BaseModel):
    """記憶のかけら追加リクエスト"""
    amount: int


class SubscriptionRequest(BaseModel):
    """月額パス購入リクエスト"""
    months: int = 1


class SetSubPersonaRequest(BaseModel):
    """サブペルソナ設定リクエスト"""
    persona_id: int
