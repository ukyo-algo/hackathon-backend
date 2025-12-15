from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.db.database import get_db

router = APIRouter()


@router.post("/context")
def post_context(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    ページ遷移のコンテキストを受け取り、ひと言メッセージを返す（スケルトン）。
    本実装では LLMService を呼び出す予定だが、現段階では簡易応答のみ返す。
    """
    uid = payload.get("uid")
    path = payload.get("path")
    query = payload.get("query")

    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    # 簡易メッセージ（LLM未接続のため）
    # 未使用変数の警告を避けるため、uid/queryも軽く含める
    q_info = f"?{query}" if query else ""
    uid_info = f" (uid: {uid})" if uid else ""
    msg = f"今は『{path}{q_info}』を見ています{uid_info}。必要ならチャットで相談してください。"
    return {"message": msg}


@router.post("/func")
def call_llm_function(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Function Callingの入口（スケルトン）。
    name と args を受け取り、プレースホルダ結果を返す。
    """
    name = payload.get("name")
    args = payload.get("args", {})

    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    if name == "check_market_price":
        item_name = args.get("item_name", "不明な商品")
        return {
            "result": {
                "source": "general_knowledge",
                "status": "insufficient_data",
                "instruction": f"『{item_name}』の一般的相場を知識ベースで答えてください。",
            }
        }
    elif name == "search_items":
        q = args.get("q", "")
        return {"result": {"items": [], "note": f"検索キーワード: {q}"}}

    return {"result": {"ok": True}}
