# backend/app/api/v1/endpoints/items.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List


from app.db.database import get_db
from app.db import models
from app.schemas import item as item_schema  # item.py をインポート

# このファイル用のAPIルーターを作成
router = APIRouter()


@router.get(
    "",  # /api/v1/items のルート
    response_model=List[item_schema.Item],  # [Item, Item, ...] のリストで返る
    summary="商品一覧取得",
)
def get_items(db: Session = Depends(get_db)):  # DBセッションを取得
    """
    全商品一覧（販売中）を新着順で取得します。

    N+1問題を回避するため、出品者情報(seller)もJOINして取得します。
    """
    items = (
        db.query(
            models.Item
        )  # Itemクラス内のtablename変数を元に，参照したいdbを指定(今回はitemsテーブルを参照することになる)
        .options(joinedload(models.Item.seller))  # relationship("seller") をJOIN
        .filter(models.Item.status == "on_sale")
        .order_by(models.Item.created_at.desc())
        .all()
    )

    return items


@router.get(
    "/{item_id}",  # /api/v1/items/{item_id} のルート
    response_model=item_schema.Item,  # 単体の Item で返る
    summary="商品詳細取得",
)
def get_item(item_id: str, db: Session = Depends(get_db)):  # URLから item_id を受け取る
    """
    指定された item_id の商品詳細を取得します。
    出品者情報(seller)もJOINして取得します。
    """
    item = (
        db.query(models.Item)
        .options(joinedload(models.Item.seller))
        .filter(models.Item.item_id == item_id)
        .first()
    )

    # 商品が見つからなかった場合、404エラーを返す
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )

    return item
