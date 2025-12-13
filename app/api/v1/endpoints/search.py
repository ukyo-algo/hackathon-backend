"""
検索エンドポイント
LLMを使用した意味的な商品検索機能を提供
"""

from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.database import SessionLocal
from app.db.models import Item
from app.schemas.item import SearchItemResponse
from app.services.llm_service import get_llm_service

router = APIRouter(prefix="/search", tags=["search"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/items", response_model=List[SearchItemResponse])
async def search_items(
    query: str = Query(..., min_length=1, max_length=100), db: Session = Depends(get_db)
):
    """
    LLMを使用した意味的な商品検索

    例: "赤いドレス" -> ファッション系の赤い商品を提案
    例: "靴" -> 靴カテゴリの商品を提案
    """

    # 全商品を取得
    all_items = db.query(Item).filter(Item.status == "on_sale").all()

    if not all_items:
        return []

    # LLMサービスインスタンスを取得
    llm_svc = get_llm_service(db)

    # LLMに検索クエリの意図を解析させて、関連商品を絞る
    search_prompt = f"""
    ユーザーが以下の検索キーワードで商品を探しています:
    "{query}"
    
    以下の商品リストから、このキーワードに関連している商品のIDを最大10個、関連度が高い順に選んでください。
    
    商品リスト:
    {_format_items_for_llm(all_items)}
    
    関連性があると判断した商品のIDだけを、改行区切りで返してください。
    例:
    123
    456
    789
    """

    try:
        response = await llm_svc.get_response(search_prompt)
        item_ids = _parse_item_ids(response, all_items)

        # IDに基づいて商品を返す
        # 順序を維持するために、IDリストの順に取得するか、取得後に並べ替える
        # ここでは簡易的に IN 句で取得 (順序は保証されないが、検索結果としては許容)
        if not item_ids:
            return []

        results = db.query(Item).filter(Item.item_id.in_(item_ids)).all()

        # SearchItemResponseに合わせて必要フィールドを整形
        response_items: List[SearchItemResponse] = []
        for it in results:
            response_items.append(
                SearchItemResponse(
                    item_id=it.item_id,
                    name=it.name,
                    price=it.price,
                    image_url=it.image_url,
                    category=it.category,
                    seller=it.seller,  # validatorでusernameに整形
                    like_count=getattr(it, "like_count", 0),
                    comment_count=getattr(it, "comments_count", 0),
                )
            )

        return response_items

    except Exception as e:
        print(f"Search Error: {e}")
        # LLM失敗時は、シンプルなテキスト検索にフォールバック
        return _fallback_search(all_items, query)


def _format_items_for_llm(items: List[Item]) -> str:
    """商品情報をLLMに渡すためにフォーマット"""
    formatted = []
    for item in items[:50]:  # 最大50商品に制限してトークン消費を抑える
        formatted.append(
            f"ID: {item.item_id}, 名前: {item.name}, "
            f"カテゴリ: {item.category}, 説明: {item.description[:100]}"
        )
    return "\n".join(formatted)


def _parse_item_ids(response: str, all_items: List[Item]) -> List[int]:
    """LLMの応答からアイテムIDを抽出"""
    # item_id は String なので注意
    valid_ids = {item.item_id for item in all_items}
    item_ids = []

    for line in response.strip().split("\n"):
        try:
            # 文字列として扱う
            item_id = line.strip()
            if item_id in valid_ids:
                item_ids.append(item_id)
        except (ValueError, AttributeError):
            continue

    return item_ids


def _fallback_search(items: List[Item], query: str) -> List[Item]:
    """LLM失敗時のフォールバック: シンプルテキスト検索"""
    query_lower = query.lower()
    results = []

    for item in items:
        # 名前、説明、カテゴリで検索
        if (
            query_lower in item.name.lower()
            or query_lower in item.description.lower()
            or query_lower in item.category.lower()
        ):
            results.append(item)

    return results
