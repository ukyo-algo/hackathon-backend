# hackathon-backend/app/services/function_tools.py
"""
LLM Function Calling用のツール定義と実行
"""

from google.genai import types
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from app.db import models


# --- Function定義 (Gemini Tool Schema) ---

FUNCTION_DECLARATIONS = [
    # ショッピング関連
    types.FunctionDeclaration(
        name="search_items",
        description="商品を検索する。ユーザーが「〜を探して」「〜ある？」と言った時に使う。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(
                    type=types.Type.STRING,
                    description="検索キーワード（例: 青い服、バッグ、Nike）",
                ),
                "category": types.Schema(
                    type=types.Type.STRING,
                    description="カテゴリで絞り込む場合（任意）",
                ),
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_item_details",
        description="商品の詳細情報を取得する。ユーザーが商品について詳しく知りたい時に使う。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "item_id": types.Schema(
                    type=types.Type.STRING,
                    description="商品ID",
                ),
            },
            required=["item_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="navigate_to_page",
        description="指定したページに遷移する。ユーザーが「〜に行きたい」「〜を見せて」と言った時に使う。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "page_name": types.Schema(
                    type=types.Type.STRING,
                    description="ページ名: home, mypage, gacha, seller, buyer, persona-selection, items/create",
                ),
            },
            required=["page_name"],
        ),
    ),
    
    # エンタメ関連
    types.FunctionDeclaration(
        name="draw_gacha",
        description="ガチャを引く。ユーザーが「ガチャ引いて」「くじ引いて」と言った時に使う。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
        ),
    ),
    types.FunctionDeclaration(
        name="get_recommendations",
        description="おすすめ商品を生成する。ユーザーが「おすすめある？」「何かいいのない？」と言った時に使う。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "keyword": types.Schema(
                    type=types.Type.STRING,
                    description="おすすめのヒントになるキーワード（任意）",
                ),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="check_balance",
        description="コイン残高を確認する。ユーザーが「残高」「コインいくら」と言った時に使う。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
        ),
    ),
    
    # 出品サポート
    types.FunctionDeclaration(
        name="suggest_price",
        description="商品の適正価格を提案する。ユーザーが「いくらで売れる？」「相場は？」と言った時に使う。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(
                    type=types.Type.STRING,
                    description="商品名",
                ),
                "category": types.Schema(
                    type=types.Type.STRING,
                    description="カテゴリ",
                ),
                "condition": types.Schema(
                    type=types.Type.STRING,
                    description="状態（新品、未使用に近い、目立った傷や汚れなし、やや傷や汚れあり、傷や汚れあり、全体的に状態が悪い）",
                ),
            },
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="generate_description",
        description="商品説明文を生成する。ユーザーが「説明書いて」「説明考えて」と言った時、または出品フォームページにいて「出品して」と言った時に使う。出品フォームページでは start_listing ではなくこちらを使う。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(
                    type=types.Type.STRING,
                    description="商品名",
                ),
                "category": types.Schema(
                    type=types.Type.STRING,
                    description="カテゴリ",
                ),
                "keywords": types.Schema(
                    type=types.Type.STRING,
                    description="説明に含めたいキーワード（任意）",
                ),
            },
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="start_listing",
        description="出品フォームに遷移して情報を自動入力する。ユーザーが「出品して」「売りたい」と言った時に使う。ただし、すでに出品フォームページ（page='items/create'）にいる場合は使わず、generate_description を使うこと。",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(
                    type=types.Type.STRING,
                    description="商品名",
                ),
                "price": types.Schema(
                    type=types.Type.INTEGER,
                    description="価格",
                ),
                "category": types.Schema(
                    type=types.Type.STRING,
                    description="カテゴリ",
                ),
                "description": types.Schema(
                    type=types.Type.STRING,
                    description="商品説明",
                ),
            },
            required=["name"],
        ),
    ),
]

# ツール定義
TOOLS = types.Tool(function_declarations=FUNCTION_DECLARATIONS)


# --- Function実行クラス ---

class FunctionExecutor:
    """Function Callingの実行を担当"""
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
    
    def execute(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """指定されたFunctionを実行"""
        method = getattr(self, f"_exec_{function_name}", None)
        if method is None:
            return {"error": f"Unknown function: {function_name}"}
        return method(**args)
    
    # --- ショッピング関連 ---
    
    def _exec_search_items(self, query: str, category: str = None) -> Dict[str, Any]:
        """商品検索"""
        q = self.db.query(models.Item).filter(models.Item.status == "on_sale")
        
        # キーワード検索
        if query:
            q = q.filter(
                models.Item.name.ilike(f"%{query}%") |
                models.Item.description.ilike(f"%{query}%")
            )
        
        # カテゴリ絞り込み
        if category:
            q = q.filter(models.Item.category == category)
        
        items = q.limit(5).all()
        
        return {
            "action": "search_items",
            "query": query,
            "count": len(items),
            "items": [
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "price": item.price,
                    "image_url": item.image_url,
                }
                for item in items
            ],
        }
    
    def _exec_get_item_details(self, item_id: str) -> Dict[str, Any]:
        """商品詳細取得"""
        item = self.db.query(models.Item).filter(
            models.Item.item_id == item_id
        ).first()
        
        if not item:
            return {"action": "get_item_details", "error": "商品が見つかりません"}
        
        return {
            "action": "get_item_details",
            "item": {
                "item_id": item.item_id,
                "name": item.name,
                "price": item.price,
                "description": item.description,
                "category": item.category,
                "brand": item.brand,
                "condition": item.condition,
                "image_url": item.image_url,
                "status": item.status,
            },
        }
    
    def _exec_navigate_to_page(self, page_name: str) -> Dict[str, Any]:
        """ページ遷移"""
        # ページ名をパスにマッピング
        page_map = {
            "home": "/",
            "mypage": "/mypage",
            "gacha": "/gacha",
            "seller": "/seller",
            "buyer": "/buyer",
            "persona-selection": "/persona-selection",
            "items/create": "/items/create",
            "mission": "/mission",
            "出品": "/items/create",
            "マイページ": "/mypage",
            "ホーム": "/",
            "ガチャ": "/gacha",
            "ミッション": "/mission",
        }
        
        path = page_map.get(page_name, page_map.get(page_name.lower(), None))
        if not path:
            path = f"/{page_name}"
        
        return {
            "action": "navigate",
            "path": path,
        }
    
    # --- エンタメ関連 ---
    
    def _exec_draw_gacha(self) -> Dict[str, Any]:
        """ガチャ実行"""
        from app.core.config import settings
        
        user = self.db.query(models.User).filter(
            models.User.firebase_uid == self.user_id
        ).first()
        
        if not user:
            return {"action": "draw_gacha", "error": "ユーザーが見つかりません"}
        
        cost = settings.GACHA_COST
        if user.gacha_points < cost:
            return {
                "action": "draw_gacha",
                "error": f"ガチャポイントが足りません（必要: {cost}ポイント、残高: {user.gacha_points}ポイント）",
            }
        
        # ポイントを消費
        user.gacha_points -= cost
        
        # ランダムにペルソナを選択
        all_personas = self.db.query(models.AgentPersona).all()
        if not all_personas:
            return {"action": "draw_gacha", "error": "キャラクターがありません"}
        
        import random
        persona = random.choice(all_personas)
        
        # 所持に追加
        existing = self.db.query(models.UserPersona).filter(
            models.UserPersona.user_id == user.id,
            models.UserPersona.persona_id == persona.id,
        ).first()
        
        if existing:
            existing.stack_count += 1
            is_new = False
        else:
            new_up = models.UserPersona(user_id=user.id, persona_id=persona.id)
            self.db.add(new_up)
            is_new = True
        
        self.db.commit()
        
        return {
            "action": "draw_gacha",
            "result": {
                "persona_id": persona.id,
                "name": persona.name,
                "rarity": persona.rarity,
                "avatar_url": persona.avatar_url,
                "is_new": is_new,
            },
            "cost_spent": cost,
            "remaining_gacha_points": user.gacha_points,
        }
    
    def _exec_get_recommendations(self, keyword: str = None) -> Dict[str, Any]:
        """おすすめ生成（ユーザー活動履歴ベース）"""
        from sqlalchemy.orm import joinedload
        from app.services import recommend_service
        
        user = self.db.query(models.User).filter(
            models.User.firebase_uid == self.user_id
        ).first()
        
        recommended_items = []
        reason = ""
        
        # 1. キーワード指定がある場合は検索ベース
        if keyword:
            items = (
                self.db.query(models.Item)
                .filter(
                    models.Item.status == "on_sale",
                    models.Item.name.ilike(f"%{keyword}%")
                )
                .limit(5)
                .all()
            )
            recommended_items = items
            reason = f"「{keyword}」に関連する商品"
        
        # 2. いいねした商品から類似商品を探す
        if not recommended_items:
            liked_item = (
                self.db.query(models.Item)
                .join(models.Like, models.Item.item_id == models.Like.item_id)
                .filter(models.Like.user_id == self.user_id)
                .order_by(models.Like.created_at.desc())
                .first()
            )
            if liked_item:
                recommended_items = recommend_service.get_recommendations(
                    self.db, liked_item.item_id, limit=5
                )
                reason = f"お気に入りの「{liked_item.name}」に似た商品"
        
        # 3. 購入履歴から類似商品を探す
        if not recommended_items:
            purchase = (
                self.db.query(models.Transaction)
                .options(joinedload(models.Transaction.item))
                .filter(models.Transaction.buyer_id == self.user_id)
                .order_by(models.Transaction.created_at.desc())
                .first()
            )
            if purchase and purchase.item:
                recommended_items = recommend_service.get_recommendations(
                    self.db, purchase.item.item_id, limit=5
                )
                reason = f"購入した「{purchase.item.name}」に似た商品"
        
        # 4. コメント履歴から関心のあるカテゴリを探す
        if not recommended_items:
            comment = (
                self.db.query(models.Comment)
                .options(joinedload(models.Comment.item))
                .filter(models.Comment.user_id == self.user_id)
                .order_by(models.Comment.created_at.desc())
                .first()
            )
            if comment and comment.item:
                category = comment.item.category
                items = (
                    self.db.query(models.Item)
                    .filter(
                        models.Item.status == "on_sale",
                        models.Item.category == category
                    )
                    .order_by(models.Item.created_at.desc())
                    .limit(5)
                    .all()
                )
                recommended_items = items
                reason = f"興味のある「{category}」カテゴリの商品"
        
        # 5. フォールバック: 人気商品（いいね数順）
        if not recommended_items:
            items = (
                self.db.query(models.Item)
                .filter(models.Item.status == "on_sale")
                .order_by(models.Item.created_at.desc())
                .limit(5)
                .all()
            )
            recommended_items = items
            reason = "新着のおすすめ商品"
        
        return {
            "action": "get_recommendations",
            "keyword": keyword,
            "reason": reason,
            "items": [
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "price": item.price,
                    "category": item.category,
                }
                for item in recommended_items[:5]
            ],
        }
    
    def _exec_check_balance(self) -> Dict[str, Any]:
        """残高確認"""
        user = self.db.query(models.User).filter(
            models.User.firebase_uid == self.user_id
        ).first()
        
        if not user:
            return {"action": "check_balance", "error": "ユーザーが見つかりません"}
        
        return {
            "action": "check_balance",
            "gacha_points": user.gacha_points,
            "memory_fragments": user.memory_fragments,
        }
    
    # --- 出品サポート ---
    
    def _exec_suggest_price(self, name: str, category: str = None, condition: str = None) -> Dict[str, Any]:
        """価格提案（類似商品の平均価格を計算）"""
        q = self.db.query(models.Item).filter(
            models.Item.name.ilike(f"%{name}%")
        )
        
        if category:
            q = q.filter(models.Item.category == category)
        
        similar_items = q.limit(10).all()
        
        if not similar_items:
            return {
                "action": "suggest_price",
                "name": name,
                "suggested_price": None,
                "message": "類似商品が見つかりませんでした。",
            }
        
        prices = [item.price for item in similar_items if item.price]
        avg_price = sum(prices) // len(prices) if prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        
        return {
            "action": "suggest_price",
            "name": name,
            "suggested_price": avg_price,
            "price_range": {"min": min_price, "max": max_price},
            "sample_count": len(similar_items),
        }
    
    def _exec_generate_description(self, name: str, category: str = None, keywords: str = None) -> Dict[str, Any]:
        """商品説明生成（フロントに指示を返す - 実際の生成はLLMが行う）"""
        return {
            "action": "generate_description",
            "name": name,
            "category": category,
            "keywords": keywords,
            "prompt": f"{name}の魅力的な商品説明を生成してください。",
        }
    
    def _exec_start_listing(
        self, name: str, price: int = None, category: str = None, description: str = None
    ) -> Dict[str, Any]:
        """出品フォームへ遷移&入力"""
        return {
            "action": "start_listing",
            "path": "/items/create",
            "prefill": {
                "name": name,
                "price": price,
                "category": category,
                "description": description,
            },
        }
