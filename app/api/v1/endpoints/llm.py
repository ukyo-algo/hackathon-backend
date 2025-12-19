# app/api/v1/endpoints/llm.py
"""
LLM関連エンドポイント
ページ遷移コンテキスト、Function Calling対応
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict, List

from app.db.database import get_db
from app.db import models
from app.services.llm_service import get_llm_service
from app.schemas.context import ContextRequest, PageContext, build_context_text

import re

router = APIRouter()


@router.post("/context")
def post_context(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    ページ遷移のコンテキストを受け取り、ペルソナ口調のひと言ガイダンスを返す。
    
    リクエストbody:
    - uid: Firebase UID
    - path: 現在のパス
    - query: クエリパラメータ
    - page_context: PageContext (オプション、フロントから送られるリッチな情報)
    """
    uid = payload.get("uid")
    path = payload.get("path")
    query = payload.get("query") or ""
    page_context_raw = payload.get("page_context")

    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    q_info = f"?{query}" if query else ""
    print(f"[llm/context] uid={uid} path={path}{q_info}")
    
    # --- ユーザー情報取得 ---
    user = (
        db.query(models.User).filter(models.User.firebase_uid == uid).first()
        if uid
        else None
    )
    
    # --- ページコンテキストの構築 ---
    context_text = ""
    
    # フロントから送られたpage_contextがあれば使用
    if page_context_raw:
        try:
            page_context = PageContext(**page_context_raw)
            context_text = build_context_text(page_context)
        except Exception as e:
            print(f"[llm/context] page_context parse error: {e}")
    
    # page_contextがない場合、従来のDB問い合わせでコンテキスト構築
    if not context_text:
        context_text = _build_legacy_context(db, user, path, query)
    
    # --- プロンプト構築（ページタイプに応じて指示を変える） ---
    page_type = page_context_raw.get("page_type") if page_context_raw else None
    
    if page_type == "gacha_result":
        # ガチャ結果時：引いたキャラについてコメント
        prompt = f"""
{context_text}

ユーザーがガチャを引きました！上記の結果を見てください。
引いたキャラクターについて、キャラクターとして以下のいずれかのリアクションをしてください：
- 新規獲得なら祝福する
- レアリティが高ければ興奮する
- 重複なら「また会えたね」的なコメント
- キャラの名前やレアリティに応じた個性的なコメント

汎用的な説明は避け、具体的なキャラ名に言及してください。
"""
    elif page_type in ("my_page", "mypage"):
        # マイページ：出品・購入状況に関する一言
        prompt = f"""
{context_text}

ユーザーがマイページを見ています。
上記の情報（出品数、購入数、いいね数など）を踏まえて、
取引状況や活動に関する一言を返してください。
ガチャやキャラクターの話は避け、フリマの取引に集中してください。
"""
    elif page_type == "seller":
        # 出品管理ページ
        prompt = f"""
{context_text}

ユーザーが出品管理ページを見ています。
出品中の商品や発送待ちについて、キャラクターとして応援やアドバイスをしてください。
"""
    elif page_type == "buyer":
        # 購入管理ページ
        prompt = f"""
{context_text}

ユーザーが購入管理ページを見ています。
購入した商品の配送状況や受け取り確認について、キャラクターとして一言添えてください。
"""
    else:
        # 通常のページ遷移
        prompt = f"""
{context_text}

ユーザーがページ「{path}{q_info}」を開きました。
上記の情報を踏まえて、キャラクターとしてユーザーに寄り添う一言を返してください。
商品を見ているなら具体的な感想や意見を述べてください。
"""

    print(f"[llm/context] prompt length: {len(prompt)}")
    print(f"[llm/context] === FULL PROMPT ===")
    print(prompt)
    print(f"[llm/context] === END PROMPT ===")

    llm_svc = get_llm_service(db)
    try:
        result = llm_svc.chat_with_persona(user_id=uid or "", current_chat=prompt)
        reply = result.get("reply")
        persona = result.get("persona")
        
        print(f"[llm/context] === LLM REPLY ===")
        print(f"[llm/context] persona: {persona}")
        print(f"[llm/context] reply: {reply}")
        print(f"[llm/context] === END REPLY ===")
        
        # ガイダンスをDB履歴に保存（replyを保存する、context_textではない）
        if uid and reply:
            try:
                llm_svc.add_guidance(uid, reply)
            except Exception:
                pass
                
        if reply:
            return {"message": reply, "persona": persona}
    except Exception as e:
        print(f"[llm/context] LLM error: {e}")

    # フォールバック
    return _fallback_response(path)


def _build_legacy_context(db: Session, user, path: str, query: str) -> str:
    """従来のDB問い合わせベースのコンテキスト構築"""
    lines = []
    
    if user:
        lines.append(f"【ユーザー】{user.username}")
        
        # ガチャポイント残高
        if hasattr(user, 'gacha_points'):
            lines.append(f"【ガチャポイント残高】{user.gacha_points:,}ポイント")
    
    # 検索クエリ
    if "q=" in query:
        search_word = query.split("q=")[-1].split("&")[0]
        lines.append(f"【検索キーワード】「{search_word}」")
    
    # アイテム詳細ページの場合
    m = re.match(r"^/items/([^/?]+)", path or "")
    if m:
        item_id = m.group(1)
        item = db.query(models.Item).filter(models.Item.item_id == item_id).first()
        if item:
            lines.append("")
            lines.append("【現在見ている商品】")
            lines.append(f"  商品名: {item.name}")
            lines.append(f"  価格: ¥{item.price:,}")
            if item.category:
                lines.append(f"  カテゴリ: {item.category}")
            if item.condition:
                lines.append(f"  状態: {item.condition}")
            if item.description:
                desc = (item.description[:200] + "...") if len(item.description or "") > 200 else item.description
                lines.append(f"  説明: {desc}")
            if item.seller:
                lines.append(f"  出品者: {item.seller.username}")
            lines.append(f"  いいね数: {getattr(item, 'like_count', 0)}")
            
            # コメント取得
            comments = getattr(item, 'comments', [])
            if comments:
                lines.append(f"  コメント数: {len(comments)}")
                lines.append("  最近のコメント:")
                for c in comments[:5]:
                    username = c.user.username if c.user else "匿名"
                    content = (c.content[:50] + "...") if len(c.content or "") > 50 else c.content
                    lines.append(f"    - {username}: 「{content}」")
    
    return "\n".join(lines)


def _fallback_response(path: str) -> Dict[str, Any]:
    """LLM失敗時のフォールバック応答"""
    lower_path = (path or "").lower()
    
    if "buyer" in lower_path:
        fb = "購入した商品の状況を確認できます。届いたら『受け取りました』で完了しましょう。"
    elif "seller" in lower_path:
        fb = "出品中の商品一覧です。発送準備ができたらステータスを更新しましょう。"
    elif "/items/" in lower_path:
        fb = "商品の詳細ページです。気になる点があれば質問してくださいね。"
    elif "gacha" in lower_path:
        fb = "ガチャで新しいキャラクターをゲットしましょう！"
    elif "mypage" in lower_path:
        fb = "マイページです。取引状況や設定を確認できます。"
    else:
        fb = "何かお探しですか？お手伝いしますよ。"
    
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

    return {"result": {"ok": True}}
