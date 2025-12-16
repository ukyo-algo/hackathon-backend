# app/schemas/context.py
"""
ページコンテキスト用スキーマ
LLMに渡すための画面情報を定義
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class CommentContext(BaseModel):
    """コメント情報"""
    username: str
    content: str


class ItemContext(BaseModel):
    """アイテム情報（LLMコンテキスト用）"""
    item_id: str
    name: str
    price: int
    category: Optional[str] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    seller_name: Optional[str] = None
    like_count: int = 0
    comment_count: int = 0
    comments: Optional[List[CommentContext]] = None  # 最新5件程度


class PageContext(BaseModel):
    """ページコンテキスト"""
    page_type: str  # "homepage" | "item_detail" | "search" | "mypage" | "gacha" | etc.
    current_item: Optional[ItemContext] = None
    visible_items: Optional[List[ItemContext]] = None
    search_query: Optional[str] = None
    user_coins: Optional[int] = None
    owned_persona_names: Optional[List[str]] = None
    additional_info: Optional[Dict[str, Any]] = None


class ContextRequest(BaseModel):
    """コンテキストAPIリクエスト"""
    uid: Optional[str] = None
    path: str
    query: Optional[str] = None
    page_context: Optional[PageContext] = None


class ChatRequestWithContext(BaseModel):
    """コンテキスト付きチャットリクエスト"""
    message: str
    page_context: Optional[PageContext] = None
    history: Optional[List[Dict[str, Any]]] = None  # 互換性維持


def build_context_text(page_context: Optional[PageContext]) -> str:
    """ページコンテキストを人間可読なテキストに変換"""
    if not page_context:
        return ""
    
    lines = []
    
    # ページタイプ
    page_type_names = {
        "homepage": "ホームページ",
        "item_detail": "商品詳細ページ",
        "search": "検索結果ページ",
        "mypage": "マイページ",
        "gacha": "ガチャページ",
        "persona_selection": "キャラクター選択ページ",
        "seller": "出品管理ページ",
        "buyer": "購入管理ページ",
    }
    page_name = page_type_names.get(page_context.page_type, page_context.page_type)
    lines.append(f"【現在のページ】{page_name}")
    
    # 検索クエリ
    if page_context.search_query:
        lines.append(f"【検索キーワード】「{page_context.search_query}」")
    
    # 現在見ている商品
    if page_context.current_item:
        item = page_context.current_item
        lines.append("")
        lines.append("【現在見ている商品】")
        lines.append(f"  商品名: {item.name}")
        lines.append(f"  価格: ¥{item.price:,}")
        if item.category:
            lines.append(f"  カテゴリ: {item.category}")
        if item.condition:
            lines.append(f"  状態: {item.condition}")
        if item.description:
            # 説明文は最初の200文字まで
            desc = item.description[:200] + ("..." if len(item.description) > 200 else "")
            lines.append(f"  説明: {desc}")
        if item.seller_name:
            lines.append(f"  出品者: {item.seller_name}")
        lines.append(f"  いいね数: {item.like_count}")
        lines.append(f"  コメント数: {item.comment_count}")
        
        # コメント表示
        if item.comments:
            lines.append("  最近のコメント:")
            for c in item.comments[:5]:
                lines.append(f"    - {c.username}: 「{c.content[:50]}」")
    
    # 表示中の商品リスト
    if page_context.visible_items:
        lines.append("")
        lines.append(f"【表示中の商品】({len(page_context.visible_items)}件)")
        for i, item in enumerate(page_context.visible_items[:10]):  # 最大10件
            lines.append(f"  {i+1}. {item.name} - ¥{item.price:,}")
    
    # ユーザー情報
    if page_context.user_coins is not None:
        lines.append("")
        lines.append(f"【ユーザーのコイン残高】{page_context.user_coins:,}コイン")
    
    if page_context.owned_persona_names:
        lines.append(f"【所有キャラクター】{', '.join(page_context.owned_persona_names)}")
    
    # 追加情報
    if page_context.additional_info:
        for key, value in page_context.additional_info.items():
            lines.append(f"【{key}】{value}")
    
    return "\n".join(lines)
