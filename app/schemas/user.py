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
