# hackathon-backend/app/api/v1/endpoints/gacha.py
"""
ガチャシステム API エンドポイント
- ガチャを引く（クーポン適用可能）
- 使用可能なクーポン一覧
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import random
from typing import Optional

from app.db.database import get_db
from app.api.v1.endpoints.users import get_current_user
from app.db import models
from app.schemas.gacha import GachaResponse, ChargeRequest, ChargeResponse
from app.schemas.user import PersonaBase
from app.db.data.personas import SKILL_DEFINITIONS
from app.services.mission_service import (
    get_valid_coupon,
    use_coupon,
    get_available_coupons,
    get_user_persona_level,
)


router = APIRouter()

# ガチャ設定
BASE_GACHA_COST = 100
GACHA_PROBABILITIES = {1: 0.40, 2: 0.30, 3: 0.15, 4: 0.10, 5: 0.05}
DUPLICATE_FRAGMENTS = {1: 5, 2: 15, 3: 30, 4: 50, 5: 100}


@router.get("/available-coupons")
def get_available_gacha_coupons(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """ガチャに使用可能なクーポン一覧を取得"""
    
    coupons = get_available_coupons(db, current_user.id, "gacha_discount")
    
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


@router.post("/charge", response_model=ChargeResponse)
def charge_points(
    request: ChargeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """ガチャポイントをチャージ（購入）する"""
    
    amount = request.amount
    if amount <= 0:
        raise HTTPException(status_code=400, detail="チャージ額は正の数である必要があります")

    # ポイント加算
    current_user.gacha_points = (current_user.gacha_points or 0) + amount
    db.commit()
    
    return {
        "success": True,
        "added_points": amount,
        "current_points": current_user.gacha_points,
        "message": f"{amount}pt をチャージしました！"
    }


@router.post("/draw", response_model=GachaResponse)
def draw_gacha(
    coupon_id: Optional[int] = Query(None, description="使用するクーポンID"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """ガチャを引くエンドポイント（クーポン適用可能）"""
    
    # 1. クーポン適用チェック
    discount_percent = 0
    used_coupon = None
    
    if coupon_id:
        coupon = get_valid_coupon(db, coupon_id, current_user.id, "gacha_discount")
        if not coupon:
            raise HTTPException(
                status_code=400,
                detail="このクーポンは使用できません（期限切れまたは既に使用済み）"
            )
        discount_percent = coupon.discount_percent
        used_coupon = coupon
    
    # 2. コスト計算＆ポイントチェック
    discount_amount = BASE_GACHA_COST * discount_percent // 100
    final_cost = BASE_GACHA_COST - discount_amount
    
    if (current_user.gacha_points or 0) < final_cost:
        raise HTTPException(
            status_code=400, 
            detail=f"ガチャポイントが足りません（必要: {final_cost}pt、所持: {current_user.gacha_points or 0}pt）"
        )
    
    # 3. ポイント消費
    current_user.gacha_points = (current_user.gacha_points or 0) - final_cost
    
    if used_coupon:
        use_coupon(used_coupon)

    # 4. ペルソナ抽選
    drawn_persona = _draw_persona(db)

    # 5. ユーザーへの付与処理
    result = _apply_gacha_result(db, current_user, drawn_persona, discount_percent)
    
    db.commit()
    
    return result


def _draw_persona(db: Session) -> models.AgentPersona:
    """ペルソナを抽選する"""
    all_personas = db.query(models.AgentPersona).all()
    if not all_personas:
        raise HTTPException(status_code=500, detail="排出対象のキャラクターがいません")
    
    # レアリティごとの候補リストを作成
    rarity_to_personas = {}
    for p in all_personas:
        rarity_to_personas.setdefault(p.rarity, []).append(p)
    
    # まずレアリティを抽選
    rarities = list(GACHA_PROBABILITIES.keys())
    probabilities = [GACHA_PROBABILITIES[r] for r in rarities]
    drawn_rarity = random.choices(rarities, weights=probabilities, k=1)[0]
    
    # そのレアリティの中からランダムに1つ選ぶ
    return random.choice(rarity_to_personas[drawn_rarity])


def _apply_gacha_result(
    db: Session,
    user: models.User,
    persona: models.AgentPersona,
    discount_percent: int,
) -> dict:
    """ガチャ結果をユーザーに適用し、レスポンスを生成"""
    
    user_persona = db.query(models.UserPersona).filter(
        models.UserPersona.user_id == user.id,
        models.UserPersona.persona_id == persona.id,
    ).first()

    is_new = False
    stack_count = 1
    fragments_earned = 0

    if user_persona:
        # 既に持っている場合 -> スタック数を増やす & 記憶のかけら付与
        user_persona.stack_count += 1
        stack_count = user_persona.stack_count
        
        # 記憶のかけら付与
        base_fragments = DUPLICATE_FRAGMENTS.get(persona.rarity, 5)
        skill_bonus = _calculate_fragment_bonus(db, user)
        fragments_earned = base_fragments + skill_bonus
        user.memory_fragments = (user.memory_fragments or 0) + fragments_earned
        
        message = f"{persona.name}が被りました！(所持数: {stack_count}) 💎記憶のかけら +{fragments_earned}個！"
    else:
        # 新規入手
        new_up = models.UserPersona(
            user_id=user.id, persona_id=persona.id, stack_count=1
        )
        db.add(new_up)
        is_new = True
        message = f"やった！{persona.name}をゲットしました！"
    
    if discount_percent > 0:
        message = f"🎟️ {discount_percent}%OFFクーポン適用！ " + message

    persona_out = PersonaBase(
        id=persona.id,
        name=persona.name,
        avatar_url=persona.avatar_url,
        description=persona.description,
        theme_color=persona.theme_color,
        rarity=persona.rarity,
        rarity_name=persona.rarity_name,
    )
    
    return {
        "persona": persona_out,
        "is_new": is_new,
        "stack_count": stack_count,
        "message": message,
        "fragments_earned": fragments_earned,
        "total_memory_fragments": user.memory_fragments or 0,
        "cost": BASE_GACHA_COST - (BASE_GACHA_COST * discount_percent // 100),
        "discount_applied": discount_percent,
    }


def _calculate_fragment_bonus(db: Session, user: models.User) -> int:
    """スキルボーナスによる記憶のかけら追加分を計算"""
    if not user.current_persona_id:
        return 0
    
    skill_def = SKILL_DEFINITIONS.get(user.current_persona_id)
    if not skill_def or skill_def.get("skill_type") != "gacha_duplicate_fragments":
        return 0
    
    level = get_user_persona_level(db, user.id, user.current_persona_id)
    base_val = skill_def.get("base_value", 0)
    max_val = skill_def.get("max_value", 0)
    
    return base_val + int((max_val - base_val) * (level - 1) / 9)
