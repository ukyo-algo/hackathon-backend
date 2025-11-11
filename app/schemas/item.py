from pydantic import BaseModel, ConfigDict
from .user import UserBase  # 上で定義したUserBaseをインポート


class ItemBase(BaseModel):
    """
    APIで商品データを返すときの基本スキーマ
    """

    item_id: str
    name: str
    description: str | None = None
    price: int
    image_url: str | None = None  # 最小構成モデルで追加したカラム
    status: str
    is_instant_buy_ok: bool

    # SQLAlchemyモデル（models.Item）からの自動変換を有効にする
    model_config = ConfigDict(from_attributes=True)


class Item(ItemBase):
    """
    APIレスポンス用のスキーマ（出品者情報を含む）
    """

    # models.Item.seller (relationship) から
    # UserBase の形に自動変換される
    seller: UserBase
