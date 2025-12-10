from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    """
    APIでユーザー情報を返すときの基本スキーマ
    """

    firebase_uid: str
    username: str
    email: EmailStr
    icon_url: str | None = None

    # SQLAlchemyモデル（models.User）から
    # Pydanticモデル（UserBase）への自動変換を有効にする
    model_config = ConfigDict(from_attributes=True)


# UserBaseを継承し、ユーザー作成時（POSTリクエスト時）に使うスキーマ
class UserCreate(UserBase):
    """
    APIがユーザー作成時にリクエストボディとして受け取るスキーマ
    """

    # UserBase の全フィールドを使用するため、ここでは追加フィールドなし
    pass


class PersonaBase(BaseModel):
    id: int
    name: str
    avatar_url: Optional[str] = None
    description: Optional[str] = None

    # ★追加: ここに書かないとフロントエンドに届きません
    theme_color: Optional[str] = "#1976d2"

    class Config:
        from_attributes = True
