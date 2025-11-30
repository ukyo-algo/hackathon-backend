from pydantic import BaseModel, ConfigDict
from .user import UserBase  # UserBaseをインポート


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
    APIレスポンス用のスキーマ（出品者情報を含む）
    """

    # ItemBaseを継承し、リレーションシップのsellerを追加
    seller: UserBase


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
