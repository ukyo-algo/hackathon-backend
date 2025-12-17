from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional


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


class UserBase(BaseModel):
    """
    APIでユーザー情報を返すときの基本スキーマ
    """

    firebase_uid: str
    username: str
    email: EmailStr
    icon_url: str | None = None
    current_persona_id: int
    current_persona: Optional["PersonaBase"] = None
    gacha_points: int = 0  # 旧名: coins
    memory_fragments: int = 0

    # SQLAlchemyモデル（models.User）から
    # Pydanticモデル（UserBase）への自動変換を有効にする
    model_config = ConfigDict(from_attributes=True)


# UserBaseを継承し、ユーザー作成時（POSTリクエスト時）に使うスキーマ
class UserCreate(UserBase):
    """
    APIがユーザー作成時にリクエストボディとして受け取るスキーマ
    """

    # 作成時は current_persona_id は必須ではない（バックエンドで設定する）
    current_persona_id: Optional[int] = None
