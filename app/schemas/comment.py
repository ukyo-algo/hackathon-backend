from pydantic import BaseModel, ConfigDict
from datetime import datetime
from .user import UserBase


# コメント投稿用
class CommentCreate(BaseModel):
    content: str


# コメント表示用
class Comment(BaseModel):
    comment_id: str
    content: str
    created_at: datetime
    user: UserBase  # コメントした人の情報

    model_config = ConfigDict(from_attributes=True)
