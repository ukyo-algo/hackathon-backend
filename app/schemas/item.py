from pydantic import BaseModel, ConfigDict, field_validator
from .user import SellerInfo  # SellerInfoをインポート
from typing import List
from .comment import Comment


class ItemBase(BaseModel):
    """
    APIで商品データを返すときの基本スキーマ (DBの全カラムを含む)
    """

    item_id: str
    name: str
    description: str | None = None
    price: int
    image_url: str | None = None
    status: str
    is_instant_buy_ok: bool

    # ↓↓↓ 新規追加フィールドを ItemBase に組み込む ↓↓↓
    category: str
    brand: str | None = None
    condition: str
    # ↑↑↑ 新規追加フィールド ↑↑↑

    # SQLAlchemyモデル（models.Item）からの自動変換を有効にする
    model_config = ConfigDict(from_attributes=True)


class Item(ItemBase):
    """
    APIレスポンス用のスキーマ（出品者情報、コメントを含む）
    """

    seller: SellerInfo
    # 追加: この商品についたコメントのリスト
    comments: List[Comment] = []
    # 追加: いいねの数（簡易実装）
    like_count: int = 0


class ItemCreate(BaseModel):
    """
    商品出品リクエスト用のスキーマ (クライアントから受け取るデータ)
    """

    # 必須フィールド
    name: str
    price: int
    category: str
    condition: str

    # 任意フィールド (NULL許容)
    description: str | None = None
    brand: str | None = None
    image_url: str | None = None

    # その他 (デフォルト値設定)
    is_instant_buy_ok: bool = True


class SearchItemResponse(BaseModel):
    """検索結果の商品情報"""

    item_id: str
    name: str
    price: int
    image_url: str | None
    category: str
    seller: dict  # {"username": str}
    like_count: int
    comment_count: int

    @field_validator("seller", mode="before")
    @classmethod
    def format_seller(cls, v):
        # ORMオブジェクト(User)が渡された場合、辞書に変換
        if hasattr(v, "username"):
            return {"username": v.username}
        # Noneの場合など
        if v is None:
            return {"username": "不明"}
        return v

    class Config:
        from_attributes = True
