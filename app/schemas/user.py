from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    firebase_uid: str
    username: str
    email: EmailStr
    icon_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


# 追加
class UserCreate(UserBase):
    pass
