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


# app/schemas/item.py の末尾に追記


# 商品出品リクエスト用のスキーマ
class ItemCreate(BaseModel):
    # 必須フィールド
    name: str
    price: int
    category: str
    condition: str
    description: str | None = None
    brand: str | None = None
    image_url: str | None = None
    is_instant_buy_ok: bool = True
