"""
検索エンドポイント
LLMを使用した意味的な商品検索機能を提供
"""

from fastapi import APIRouter, Query, Depends
import traceback
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
    print(f"[search] start query={query}")
    all_items = db.query(Item).filter(Item.status == "on_sale").all()
    print(f"[search] fetched on_sale items count={len(all_items)}")

    if not all_items:
        return []

    # LLMサービスインスタンスを取得
    llm_svc = get_llm_service(db)
    print("[search] llm service acquired")

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
        print("[search] calling llm_svc.chat_with_persona")
        # chat_with_personaは同期関数なのでawait不要
        chat_result = llm_svc.chat_with_persona(
            user_id=None, message=search_prompt, history=None  # 検索時はユーザーID不要
        )
        response = chat_result["reply"]
        print(f"[search] llm response len={len(response)} sample={response[:100]!r}")
        item_ids = _parse_item_ids(response, all_items)
        print(f"[search] parsed item_ids count={len(item_ids)} ids={item_ids}")

        # IDに基づいて商品を返す
        # 順序を維持するために、IDリストの順に取得するか、取得後に並べ替える
        # ここでは簡易的に IN 句で取得 (順序は保証されないが、検索結果としては許容)
        if not item_ids:
            return []

        results = db.query(Item).filter(Item.item_id.in_(item_ids)).all()
        print(f"[search] db fetch by ids count={len(results)}")

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

        print(f"[search] response_items built count={len(response_items)}")
        return response_items

    except Exception as e:
        print(f"[search] Exception in LLM or building response: {e}")
        traceback.print_exc()
        # LLM失敗時は、シンプルなテキスト検索にフォールバック
        print("[search] entering fallback search")
        fallback = _fallback_search(all_items, query)
        print(f"[search] fallback results count={len(fallback)}")
        return fallback


def _format_items_for_llm(items: List[Item]) -> str:
    """商品情報をLLMに渡すためにフォーマット"""
    formatted = []
    for item in items[:50]:  # 最大50商品に制限してトークン消費を抑える
        formatted.append(
            f"ID: {item.item_id}, 名前: {item.name}, "
            f"カテゴリ: {item.category}, 説明: {(item.description or '')[:100]}"
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


def _fallback_search(items: List[Item], query: str) -> List[SearchItemResponse]:
    query_lower = query.lower()
    results: List[SearchItemResponse] = []

    for item in items:
        name_ok = query_lower in (item.name or "").lower()
        desc_ok = query_lower in (item.description or "").lower()
        cat_ok = query_lower in (item.category or "").lower()

        if name_ok or desc_ok or cat_ok:
            results.append(
                SearchItemResponse(
                    item_id=item.item_id,
                    name=item.name,
                    price=item.price,
                    image_url=item.image_url,
                    category=item.category,
                    seller=item.seller,  # validatorで {"username": "..."} に整形
                    like_count=getattr(item, "like_count", 0),
                    comment_count=getattr(item, "comments_count", 0),
                )
            )

    return results
