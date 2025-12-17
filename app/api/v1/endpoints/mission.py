# hackathon-backend/app/api/v1/endpoints/mission.py
"""
ミッション＆デイリークーポンシステム
"""

from datetime import datetime, timedelta, timezone, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db import models
from app.api.v1.endpoints.users import get_current_user
from app.db.data.personas import SKILL_DEFINITIONS


router = APIRouter()


# =============================================================================
# デイリークーポン受け取り
# =============================================================================

@router.post("/daily-coupon/claim")
def claim_daily_coupon(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    デイリークーポンを受け取る
    - 1日1回のみ
    - 装備中のペルソナのスキルに応じたクーポンが発行される
    """
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    now_jst = datetime.now(jst)
    today = now_jst.date()
    
    # 1. 今日すでにクーポンを受け取っているか確認
    existing_coupon = (
        db.query(models.UserCoupon)
        .filter(
            models.UserCoupon.user_id == current_user.id,
            models.UserCoupon.created_at >= datetime.combine(today, datetime.min.time()).replace(tzinfo=jst),
        )
        .first()
    )
    
    if existing_coupon:
        return {
            "success": False,
            "message": "今日はすでにデイリークーポンを受け取りました",
            "next_available": "明日0時以降",
        }
    
    # 2. 装備中のペルソナのスキルを確認
    if not current_user.current_persona_id:
        return {
            "success": False,
            "message": "ペルソナを装備してからクーポンを受け取ってください",
        }
    
    skill_def = SKILL_DEFINITIONS.get(current_user.current_persona_id)
    
    # 3. スキルに応じたクーポン発行
    coupon_type = None
    discount_percent = 0
    expires_hours = 3
    
    if skill_def:
        skill_type = skill_def.get("skill_type")
        
        # 現在のペルソナのレベルを取得
        user_persona = db.query(models.UserPersona).filter(
            models.UserPersona.user_id == current_user.id,
            models.UserPersona.persona_id == current_user.current_persona_id,
        ).first()
        level = user_persona.level if user_persona else 1
        
        if skill_type == "daily_shipping_coupon":
            # 送料割引クーポン
            coupon_type = "shipping_discount"
            discount_percent = skill_def.get("discount_percent", 5)
            base_hours = skill_def.get("base_hours", 3)
            max_hours = skill_def.get("max_hours", 12)
            expires_hours = base_hours + int((max_hours - base_hours) * (level - 1) / 9)
            
        elif skill_type == "daily_gacha_discount":
            # ガチャ割引クーポン
            coupon_type = "gacha_discount"
            base_val = skill_def.get("base_value", 10)
            max_val = skill_def.get("max_value", 30)
            discount_percent = base_val + int((max_val - base_val) * (level - 1) / 9)
            expires_hours = 24
    
    # 4. クーポンがないスキルの場合はデフォルトクーポン
    if not coupon_type:
        # デフォルト: 送料5%OFF、3時間有効
        coupon_type = "shipping_discount"
        discount_percent = 5
        expires_hours = 3
    
    # 5. クーポン作成
    expires_at = now_jst + timedelta(hours=expires_hours)
    
    new_coupon = models.UserCoupon(
        user_id=current_user.id,
        coupon_type=coupon_type,
        discount_percent=discount_percent,
        expires_at=expires_at,
        issued_by_persona_id=current_user.current_persona_id,
    )
    db.add(new_coupon)
    db.commit()
    db.refresh(new_coupon)
    
    # 6. レスポンス
    coupon_name = "送料割引" if coupon_type == "shipping_discount" else "ガチャ割引"
    
    return {
        "success": True,
        "message": f"🎫 {coupon_name} {discount_percent}%OFFクーポンを獲得！",
        "coupon": {
            "id": new_coupon.id,
            "type": coupon_type,
            "discount_percent": discount_percent,
            "expires_at": expires_at.isoformat(),
            "expires_hours": expires_hours,
        }
    }


# =============================================================================
# 所持クーポン一覧
# =============================================================================

@router.get("/coupons")
def get_my_coupons(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    所持しているクーポン一覧（未使用のみ）
    """
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    now_jst = datetime.now(jst)
    
    coupons = (
        db.query(models.UserCoupon)
        .filter(
            models.UserCoupon.user_id == current_user.id,
            models.UserCoupon.used_at == None,
            models.UserCoupon.expires_at > now_jst,
        )
        .order_by(models.UserCoupon.expires_at.asc())
        .all()
    )
    
    return {
        "coupons": [
            {
                "id": c.id,
                "type": c.coupon_type,
                "discount_percent": c.discount_percent,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            }
            for c in coupons
        ]
    }


# =============================================================================
# ミッション一覧
# =============================================================================

@router.get("/missions")
def get_missions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    現在のミッション状況を取得
    """
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    now_jst = datetime.now(jst)
    today = now_jst.date()
    
    # 今日のクーポン受け取り状況
    today_coupon = (
        db.query(models.UserCoupon)
        .filter(
            models.UserCoupon.user_id == current_user.id,
            models.UserCoupon.created_at >= datetime.combine(today, datetime.min.time()).replace(tzinfo=jst),
        )
        .first()
    )
    
    # 装備中のペルソナ情報
    equipped_persona = None
    expected_coupon = {"type": "shipping_discount", "discount_percent": 5, "hours": 3}
    
    if current_user.current_persona_id:
        persona = db.query(models.AgentPersona).filter(
            models.AgentPersona.id == current_user.current_persona_id
        ).first()
        
        if persona:
            equipped_persona = {
                "id": persona.id,
                "name": persona.name,
                "avatar_url": persona.avatar_url,
            }
            
            # 期待されるクーポン
            skill_def = SKILL_DEFINITIONS.get(persona.id)
            if skill_def:
                user_persona = db.query(models.UserPersona).filter(
                    models.UserPersona.user_id == current_user.id,
                    models.UserPersona.persona_id == persona.id,
                ).first()
                level = user_persona.level if user_persona else 1
                
                skill_type = skill_def.get("skill_type")
                if skill_type == "daily_shipping_coupon":
                    discount = skill_def.get("discount_percent", 5)
                    base_hours = skill_def.get("base_hours", 3)
                    max_hours = skill_def.get("max_hours", 12)
                    hours = base_hours + int((max_hours - base_hours) * (level - 1) / 9)
                    expected_coupon = {"type": "shipping_discount", "discount_percent": discount, "hours": hours}
                elif skill_type == "daily_gacha_discount":
                    base_val = skill_def.get("base_value", 10)
                    max_val = skill_def.get("max_value", 30)
                    discount = base_val + int((max_val - base_val) * (level - 1) / 9)
                    expected_coupon = {"type": "gacha_discount", "discount_percent": discount, "hours": 24}
    
    return {
        "missions": [
            {
                "id": "daily_coupon",
                "name": "デイリークーポン受取",
                "description": f"装備中のペルソナに応じたクーポンがもらえます",
                "completed": today_coupon is not None,
                "reward_preview": expected_coupon,
            },
        ],
        "equipped_persona": equipped_persona,
        "memory_fragments": current_user.memory_fragments or 0,
        "gacha_points": current_user.gacha_points or 0,
    }
