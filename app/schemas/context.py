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
    page_type: str  # "homepage" | "item_detail" | "search" | "mypage" | "gacha" | "gacha_result" | "direct_message" | etc.
    current_item: Optional[ItemContext] = None
    visible_items: Optional[List[ItemContext]] = None
    search_query: Optional[str] = None
    user_gacha_points: Optional[int] = None  # 旧名: user_coins
    owned_persona_names: Optional[List[str]] = None
    additional_info: Optional[Dict[str, Any]] = None
    # ガチャ結果用フィールド
    result_persona_name: Optional[str] = None
    result_rarity: Optional[int] = None
    result_rarity_name: Optional[str] = None
    result_is_new: Optional[bool] = None
    result_stack_count: Optional[int] = None
    fragments_earned: Optional[int] = None
    # DM用フィールド
    dm_context: Optional[Dict[str, Any]] = None


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
        "search_results": "検索結果ページ",
        "mypage": "マイページ",
        "my_page": "マイページ",
        "gacha": "ガチャページ",
        "gacha_result": "ガチャ結果",
        "persona_selection": "キャラクター選択ページ",
        "seller": "出品管理ページ",
        "seller_shipments": "出品管理ページ",
        "buyer": "購入管理ページ",
        "buyer_deliveries": "購入管理ページ",
        "mission": "ミッションページ",
        "buy_confirmation": "購入確認ページ",
        "levelup": "レベルアップ",
        "direct_message": "ダイレクトメッセージ",
    }
    page_name = page_type_names.get(page_context.page_type, page_context.page_type)
    lines.append(f"【現在のページ】{page_name}")
    
    # ガチャ結果（新規追加）
    if page_context.page_type == "gacha_result" and page_context.result_persona_name:
        lines.append("")
        lines.append("【ガチャ結果】")
        lines.append(f"  引いたキャラクター: {page_context.result_persona_name}")
        if page_context.result_rarity_name:
            lines.append(f"  レアリティ: {page_context.result_rarity_name}")
        if page_context.result_is_new:
            lines.append("  ★新規獲得！")
        else:
            if page_context.result_stack_count:
                lines.append(f"  重複: {page_context.result_stack_count}体目")
            if page_context.fragments_earned:
                lines.append(f"  メモリーフラグメント獲得: +{page_context.fragments_earned}")
    
    # ダイレクトメッセージコンテキスト
    if page_context.page_type == "direct_message" and page_context.dm_context:
        dm = page_context.dm_context
        lines.append("")
        if dm.get("conversation_with"):
            lines.append(f"【会話相手】{dm['conversation_with']}")
        if dm.get("item_name"):
            lines.append(f"【関連商品】{dm['item_name']}")
        
        # 関係情報
        if dm.get("relationship"):
            rel = dm["relationship"]
            rel_parts = []
            if rel.get("purchases", {}).get("from_other"):
                rel_parts.append(f"相手から{len(rel['purchases']['from_other'])}件購入済み")
            if rel.get("purchases", {}).get("to_other"):
                rel_parts.append(f"相手に{len(rel['purchases']['to_other'])}件販売済み")
            if rel.get("likes", {}).get("i_liked_their_items"):
                rel_parts.append(f"相手の商品に{rel['likes']['i_liked_their_items']}いいね")
            if rel.get("likes", {}).get("they_liked_my_items"):
                rel_parts.append(f"相手から{rel['likes']['they_liked_my_items']}いいね")
            if rel_parts:
                lines.append(f"【二人の関係】{', '.join(rel_parts)}")
        
        # 直近のメッセージ
        if dm.get("recent_messages"):
            lines.append("【直近の会話】")
            for msg in dm["recent_messages"][-5:]:  # 最新5件
                sender = msg.get("sender", "?")
                content = msg.get("content", "")[:50]
                lines.append(f"  {sender}: {content}")
        
        # 指示（重要：AIにこれに従うよう明示）
        if dm.get("instruction"):
            lines.append("")
            lines.append(f"【重要な指示】{dm['instruction']}")
    
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
    if page_context.user_gacha_points is not None:
        lines.append("")
        lines.append(f"【ユーザーのガチャポイント残高】{page_context.user_gacha_points:,}ポイント")
    
    if page_context.owned_persona_names:
        lines.append(f"【所有キャラクター】{', '.join(page_context.owned_persona_names)}")
    
    # 追加情報
    if page_context.additional_info:
        for key, value in page_context.additional_info.items():
            lines.append(f"【{key}】{value}")
    
    return "\n".join(lines)
