from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict, List

from app.db.database import get_db
from app.db import models
from app.services.llm_service import get_llm_service

router = APIRouter()


@router.post("/context")
def post_context(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    ページ遷移のコンテキストを受け取り、ペルソナ口調のひと言ガイダンスを返す。
    Gemini未設定時はフォールバック文で応答します。
    """
    uid = payload.get("uid")
    path = payload.get("path")
    query = payload.get("query") or ""

    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    q_info = f"?{query}" if query else ""
    prompt = (
        f"ユーザーがページ『{path}{q_info}』を開きました。"
        "このページの目的と、ユーザーが次に取るべき具体的な一歩を日本語で1文、親切に提案してください。"
    )

    llm_svc = get_llm_service(db)
    try:
        result = llm_svc.chat_with_persona(user_id=uid or "", message=prompt)
        reply = result.get("reply")
        persona = result.get("persona")
        if reply:
            return {"message": reply, "persona": persona}
    except Exception:
        # LLM側が未設定/失敗時は下のフォールバックに移行
        pass

    # フォールバック: ページに応じた1文ガイダンスを返す
    lower_path = (path or "").lower()
    if "buyer" in lower_path:
        fb = (
            "購入者向けの取引一覧です。配送状況を確認し、商品を受け取ったら"
            "『受け取りました』で取引を完了しましょう。"
        )
    elif "seller" in lower_path:
        fb = (
            "出品者向けの取引一覧です。発送の準備ができたら『発送しました』で"
            "購入者へステータスを更新しましょう。"
        )
    else:
        fb = (
            "このページの目的に沿って次の一歩を進めましょう。"
            "必要であれば右下のチャットで相談できます。"
        )
    return {
        "message": fb,
        "persona": {"name": "ガイド", "avatar_url": "/avatars/default.png"},
    }


@router.post("/func")
def call_llm_function(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Function Callingの入口。
    name と args に応じて簡易ツールを実行します。
    """
    name = payload.get("name")
    args = payload.get("args", {})

    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    if name == "check_market_price":
        item_name = (args.get("item_name") or "").strip()
        if not item_name:
            raise HTTPException(
                status_code=400,
                detail="args.item_name is required",
            )

        # on_sale の部分一致で価格集計
        q = db.query(models.Item).filter(models.Item.status == "on_sale")
        q = q.filter(models.Item.name.ilike(f"%{item_name}%"))
        items: List[models.Item] = q.all()

        count = len(items)
        avg = (sum(it.price for it in items) / count) if count > 0 else None
        sample = [
            {"item_id": it.item_id, "name": it.name, "price": it.price}
            for it in items[:5]
        ]
        return {
            "result": {
                "status": "ok" if count > 0 else "no_data",
                "query": item_name,
                "count": count,
                "average_price": avg,
                "samples": sample,
            }
        }

    if name == "search_items":
        qstr = (args.get("q") or "").strip()
        if not qstr:
            raise HTTPException(status_code=400, detail="args.q is required")

        q_lower = qstr.lower()
        items: List[models.Item] = (
            db.query(models.Item).filter(models.Item.status == "on_sale").all()
        )

        def match(it: models.Item) -> bool:
            return (
                q_lower in (it.name or "").lower()
                or q_lower in (it.description or "").lower()
                or q_lower in (it.category or "").lower()
            )

        results = [
            {
                "item_id": it.item_id,
                "name": it.name,
                "price": it.price,
                "image_url": it.image_url,
                "category": it.category,
                "seller": {"username": getattr(it.seller, "username", "")},
                "like_count": getattr(it, "like_count", 0),
                "comment_count": getattr(it, "comments_count", 0),
            }
            for it in items
            if match(it)
        ][:20]

        return {"result": {"items": results, "query": qstr}}

    # 未対応の関数はOKのみ返す
    return {"result": {"ok": True}}
