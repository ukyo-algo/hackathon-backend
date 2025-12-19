# hackathon-backend/app/api/v1/endpoints/items.py
"""
商品関連 API エンドポイント
- 商品一覧・詳細
- 出品・購入
- いいね・コメント
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.db.database import get_db
from app.db import models
from app.schemas import item as item_schema
from app.schemas import transaction as transaction_schema
from app.schemas import comment as comment_schema
from app.api.v1.endpoints.users import get_current_user
from app.services import recommend_service
from app.services.mission_service import (
    get_valid_coupon,
    use_coupon,
    get_available_coupons,
    get_user_persona_level,
)
from app.db.data.personas import SKILL_DEFINITIONS


router = APIRouter()


# =============================================================================
# 商品一覧・詳細
# =============================================================================

@router.get("", response_model=List[item_schema.Item], summary="商品一覧取得")
def get_items(db: Session = Depends(get_db)):
    """全商品一覧（販売中）を新着順で取得"""
    return (
        db.query(models.Item)
        .options(joinedload(models.Item.seller))
        .filter(models.Item.status == "on_sale")
        .order_by(models.Item.created_at.desc())
        .all()
    )


@router.get("/{item_id}", response_model=item_schema.Item)
def get_item(item_id: str, db: Session = Depends(get_db)):
    """商品詳細を取得"""
    item = (
        db.query(models.Item)
        .options(
            joinedload(models.Item.seller),
            joinedload(models.Item.comments).joinedload(models.Comment.user),
        )
        .filter(models.Item.item_id == item_id)
        .first()
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


# =============================================================================
# 出品
# =============================================================================

@router.post("", response_model=item_schema.Item, summary="新規商品出品", status_code=status.HTTP_201_CREATED)
def create_item(
    item_in: item_schema.ItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """ログイン中のユーザーとして新しい商品を出品"""
    new_item = models.Item(
        **item_in.model_dump(),
        seller_id=current_user.firebase_uid,
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item, attribute_names=["seller"])
    return new_item


# =============================================================================
# 購入
# =============================================================================

@router.get("/{item_id}/available-coupons", summary="購入に使用可能なクーポン一覧")
def get_available_shipping_coupons(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """購入に使用可能な送料割引クーポン一覧を取得"""
    coupons = get_available_coupons(db, current_user.id, "shipping_discount")
    
    return {
        "coupons": [
            {
                "id": c.id,
                "discount_percent": c.discount_percent,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            }
            for c in coupons
        ]
    }


@router.post(
    "/{item_id}/buy",
    response_model=transaction_schema.Transaction,
    summary="商品の購入（取引成立）",
    status_code=status.HTTP_201_CREATED,
)
def buy_item(
    item_id: str,
    coupon_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    商品を購入
    - 送料割引クーポンを適用可能
    - 購入金額の10%をガチャポイントとして付与（スキルボーナス込み）
    """
    # 1. 商品を取得
    item = db.query(models.Item).filter(models.Item.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="商品が見つかりません")

    # 2. バリデーション
    if item.status != "on_sale":
        raise HTTPException(status_code=400, detail="この商品は既に売り切れています")
    if item.seller_id == current_user.firebase_uid:
        raise HTTPException(status_code=400, detail="自分の商品は購入できません")
    
    # 3. クーポン適用チェック
    if coupon_id:
        coupon = get_valid_coupon(db, coupon_id, current_user.id, "shipping_discount")
        if not coupon:
            raise HTTPException(
                status_code=400,
                detail="このクーポンは使用できません（期限切れまたは既に使用済み）"
            )
        use_coupon(coupon)

    # 4. 購入処理
    item.status = "sold"
    
    transaction = models.Transaction(
        item_id=item.item_id,
        buyer_id=current_user.firebase_uid,
        price=item.price,
        status="pending_shipment",
    )

    # 5. 購入報酬
    reward = _calculate_purchase_reward(db, current_user, item)
    current_user.gacha_points = (current_user.gacha_points or 0) + reward

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # 6. 出品者に購入通知を送信
    if item.seller:
        notification = models.Notification(
            user_id=item.seller.id,
            type="purchase",
            title="商品が売れました！",
            message=f"{current_user.username or 'ユーザー'}さんが「{item.name}」を購入しました",
            link=f"/seller",
        )
        db.add(notification)
        db.commit()

    return transaction


def _calculate_purchase_reward(db: Session, user: models.User, item: models.Item) -> int:
    """購入報酬を計算（基本10% + スキルボーナス）"""
    base_reward = item.price // 10
    
    if not user.current_persona_id:
        return base_reward
    
    skill_def = SKILL_DEFINITIONS.get(user.current_persona_id)
    if not skill_def or skill_def.get("skill_type") != "purchase_bonus_percent":
        return base_reward
    
    # カテゴリチェック
    categories = skill_def.get("categories")
    if categories and item.category and not any(cat in item.category for cat in categories):
        return base_reward
    
    # スキルボーナス計算
    level = get_user_persona_level(db, user.id, user.current_persona_id)
    base_val = skill_def.get("base_value", 0)
    max_val = skill_def.get("max_value", 0)
    skill_bonus_percent = base_val + int((max_val - base_val) * (level - 1) / 9)
    
    skill_bonus = item.price * skill_bonus_percent // 100
    return base_reward + skill_bonus


# =============================================================================
# レコメンド
# =============================================================================

@router.get("/{item_id}/recommend", response_model=List[item_schema.Item], summary="おすすめ商品の取得")
def get_recommend_items(item_id: str, db: Session = Depends(get_db)):
    """指定された商品に類似したおすすめ商品を取得"""
    return recommend_service.get_recommendations(db, item_id, limit=3)


# =============================================================================
# いいね
# =============================================================================

@router.post("/{item_id}/like", summary="いいね！のトグル")
def toggle_like(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """いいねの登録/解除"""
    existing_like = db.query(models.Like).filter(
        models.Like.item_id == item_id,
        models.Like.user_id == current_user.firebase_uid,
    ).first()

    if existing_like:
        db.delete(existing_like)
        db.commit()
        return {"status": "unliked"}
    else:
        db.add(models.Like(item_id=item_id, user_id=current_user.firebase_uid))
        db.commit()
        return {"status": "liked"}


# =============================================================================
# コメント
# =============================================================================

@router.post("/{item_id}/comments", response_model=comment_schema.Comment, summary="コメント投稿")
def create_comment(
    item_id: str,
    comment_in: comment_schema.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """商品にコメントを投稿"""
    item = db.query(models.Item).filter(models.Item.item_id == item_id).first()
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")

    new_comment = models.Comment(
        item_id=item_id,
        user_id=current_user.firebase_uid,
        content=comment_in.content,
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # 自分の商品でなければ出品者に通知を送信
    if item.seller_id != current_user.firebase_uid and item.seller:
        notification = models.Notification(
            user_id=item.seller.id,
            type="comment",
            title="新しいコメント",
            message=f"{current_user.username or 'ユーザー'}さんが「{item.name}」にコメントしました",
            link=f"/items/{item_id}",
        )
        db.add(notification)
        db.commit()

    return new_comment

