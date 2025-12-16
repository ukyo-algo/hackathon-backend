"""
検索エンドポイント
シンプルなテキストマッチ検索機能を提供
"""

from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List

from app.db.database import SessionLocal
from app.db.models import Item
from app.schemas.item import SearchItemResponse

router = APIRouter(prefix="/search", tags=["search"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/items", response_model=List[SearchItemResponse])
async def search_items(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    シンプルなテキストマッチ検索
    
    商品名、説明文、カテゴリに対して部分一致検索を行います。
    例: "赤いドレス" -> 名前や説明に「赤」「ドレス」を含む商品を返す
    """
    
    print(f"[search] start query={query}")
    
    # クエリをスペースで分割して複数キーワードに対応
    keywords = query.lower().split()
    
    # ベースクエリ: 販売中の商品のみ
    base_query = db.query(Item).filter(Item.status == "on_sale")
    
    # 各キーワードについて、名前・説明・カテゴリのいずれかに含まれるか確認
    for keyword in keywords:
        search_pattern = f"%{keyword}%"
        base_query = base_query.filter(
            or_(
                func.lower(Item.name).like(search_pattern),
                func.lower(Item.description).like(search_pattern),
                func.lower(Item.category).like(search_pattern),
            )
        )
    
    # 結果を取得（上限付き）
    results = base_query.limit(limit).all()
    print(f"[search] found {len(results)} items")
    
    # SearchItemResponseに整形して返す
    response_items: List[SearchItemResponse] = []
    for item in results:
        response_items.append(
            SearchItemResponse(
                item_id=item.item_id,
                name=item.name,
                price=item.price,
                image_url=item.image_url,
                category=item.category,
                seller=item.seller,
                like_count=getattr(item, "like_count", 0),
                comment_count=getattr(item, "comments_count", 0),
            )
        )
    
    print(f"[search] returning {len(response_items)} items")
    return response_items
