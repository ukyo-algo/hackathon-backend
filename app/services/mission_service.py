# hackathon-backend/app/services/mission_service.py
"""
ミッションシステムのビジネスロジック
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.db import models
from app.utils.time_utils import get_jst_now, is_same_day_jst, is_consecutive_day_jst, days_since_jst
from app.db.data.personas import SKILL_DEFINITIONS


# ミッション報酬定義
MISSION_REWARDS = {
    "daily_login": {"gacha_points": 50, "description": "デイリーログインボーナス"},
    "first_listing": {"gacha_points": 200, "description": "初めての出品"},
    "first_purchase": {"gacha_points": 200, "description": "初めての購入"},
    "login_streak_3": {"gacha_points": 100, "description": "連続ログイン3日達成"},
    "weekly_likes": {"gacha_points": 30, "description": "週間いいね5回達成"},
}


def has_completed_mission(db: Session, user_id: int, mission_key: str) -> bool:
    """ワンタイムミッション達成済みかどうか"""
    return db.query(models.UserMission).filter(
        models.UserMission.user_id == user_id,
        models.UserMission.mission_key == mission_key,
    ).first() is not None


def complete_mission(db: Session, user_id: int, mission_key: str) -> models.UserMission:
    """ワンタイムミッション達成を記録"""
    mission = models.UserMission(
        user_id=user_id,
        mission_key=mission_key,
    )
    db.add(mission)
    return mission


def add_gacha_points(user: models.User, points: int) -> int:
    """ガチャポイントを付与し、新しい残高を返す"""
    user.gacha_points = (user.gacha_points or 0) + points
    return user.gacha_points


def get_user_persona_level(db: Session, user_id: int, persona_id: int) -> int:
    """ユーザーのペルソナレベルを取得"""
    user_persona = db.query(models.UserPersona).filter(
        models.UserPersona.user_id == user_id,
        models.UserPersona.persona_id == persona_id,
    ).first()
    return user_persona.level if user_persona else 1


def calculate_coupon_params(
    db: Session, 
    user: models.User
) -> Dict[str, Any]:
    """
    ユーザーの装備ペルソナに基づいてクーポンパラメータを計算
    
    Returns:
        {
            "coupon_type": "shipping_discount" or "gacha_discount",
            "discount_percent": int,
            "expires_hours": int,
        }
    """
    # デフォルト値
    result = {
        "coupon_type": "shipping_discount",
        "discount_percent": 5,
        "expires_hours": 3,
    }
    
    if not user.current_persona_id:
        return result
    
    skill_def = SKILL_DEFINITIONS.get(user.current_persona_id)
    if not skill_def:
        return result
    
    level = get_user_persona_level(db, user.id, user.current_persona_id)
    skill_type = skill_def.get("skill_type")
    
    if skill_type == "daily_shipping_coupon":
        result["coupon_type"] = "shipping_discount"
        result["discount_percent"] = skill_def.get("discount_percent", 5)
        base_hours = skill_def.get("base_hours", 3)
        max_hours = skill_def.get("max_hours", 12)
        result["expires_hours"] = base_hours + int((max_hours - base_hours) * (level - 1) / 9)
        
    elif skill_type == "daily_gacha_discount":
        result["coupon_type"] = "gacha_discount"
        base_val = skill_def.get("base_value", 10)
        max_val = skill_def.get("max_value", 30)
        result["discount_percent"] = base_val + int((max_val - base_val) * (level - 1) / 9)
        result["expires_hours"] = 24
    
    return result


def create_coupon(
    db: Session,
    user: models.User,
    coupon_type: str,
    discount_percent: int,
    expires_hours: int,
    issued_by_persona_id: Optional[int] = None,
) -> models.UserCoupon:
    """クーポンを作成"""
    now_jst = get_jst_now()
    expires_at = now_jst + timedelta(hours=expires_hours)
    
    coupon = models.UserCoupon(
        user_id=user.id,
        coupon_type=coupon_type,
        discount_percent=discount_percent,
        expires_at=expires_at,
        issued_by_persona_id=issued_by_persona_id,
    )
    db.add(coupon)
    return coupon


def get_valid_coupon(
    db: Session,
    coupon_id: int,
    user_id: int,
    coupon_type: str,
) -> Optional[models.UserCoupon]:
    """有効なクーポンを取得（未使用・期限内）"""
    now_jst = get_jst_now()
    
    return db.query(models.UserCoupon).filter(
        models.UserCoupon.id == coupon_id,
        models.UserCoupon.user_id == user_id,
        models.UserCoupon.coupon_type == coupon_type,
        models.UserCoupon.used_at == None,
        models.UserCoupon.expires_at > now_jst,
    ).first()


def use_coupon(coupon: models.UserCoupon) -> None:
    """クーポンを使用済みにする"""
    coupon.used_at = get_jst_now()


def get_available_coupons(
    db: Session,
    user_id: int,
    coupon_type: str,
) -> list:
    """使用可能なクーポン一覧を取得"""
    now_jst = get_jst_now()
    
    return db.query(models.UserCoupon).filter(
        models.UserCoupon.user_id == user_id,
        models.UserCoupon.coupon_type == coupon_type,
        models.UserCoupon.used_at == None,
        models.UserCoupon.expires_at > now_jst,
    ).order_by(models.UserCoupon.discount_percent.desc()).all()
