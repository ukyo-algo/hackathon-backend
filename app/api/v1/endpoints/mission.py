# hackathon-backend/app/api/v1/endpoints/mission.py
"""
ミッション＆デイリークーポンシステム API エンドポイント

ミッション一覧:
- デイリーログインボーナス (50pt, 毎日)
- デイリークーポン受取 (ペルソナ依存, 毎日)
- 初出品ボーナス (200pt, 一回限り)
- 初購入ボーナス (200pt, 一回限り)
- 連続ログイン3日 (100pt + クーポン, 一回限り)
- 週間いいね5回 (30pt, 毎週)
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db import models
from app.api.v1.endpoints.users import get_current_user
from app.db.data.personas import SKILL_DEFINITIONS
from app.utils.time_utils import (
    get_jst_now, get_jst_today, is_same_day_jst, 
    is_consecutive_day_jst, days_since_jst, JST
)
from app.services.mission_service import (
    MISSION_REWARDS,
    has_completed_mission,
    complete_mission,
    add_gacha_points,
    calculate_coupon_params,
    create_coupon,
    get_user_persona_level,
)


router = APIRouter()


# =============================================================================
# デイリーログインボーナス
# =============================================================================

@router.post("/daily-login/claim")
def claim_daily_login(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """デイリーログインボーナスを受け取る (1日1回50pt)"""
    
    # 今日すでに受け取っているか確認
    if is_same_day_jst(current_user.last_login_bonus_at):
        return {
            "success": False,
            "message": "今日はすでにログインボーナスを受け取りました",
            "next_available": "明日0時以降",
        }
    
    # 連続ログイン判定
    if is_consecutive_day_jst(current_user.last_login_bonus_at):
        current_user.login_streak = (current_user.login_streak or 0) + 1
    else:
        current_user.login_streak = 1
    
    # 累計ログイン日数
    current_user.total_login_days = (current_user.total_login_days or 0) + 1
    
    # ログインボーナス付与
    reward = MISSION_REWARDS["daily_login"]["gacha_points"]
    add_gacha_points(current_user, reward)
    current_user.last_login_bonus_at = get_jst_now()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎫 ログインボーナス +{reward}ポイント獲得！",
        "reward": {"gacha_points": reward},
        "login_streak": current_user.login_streak,
        "total_login_days": current_user.total_login_days,
    }


# =============================================================================
# デイリークーポン受け取り
# =============================================================================

@router.post("/daily-coupon/claim")
def claim_daily_coupon(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """デイリークーポンを受け取る (1日1回、ペルソナ依存)"""
    
    today = get_jst_today()
    
    # 今日すでにクーポンを受け取っているか確認
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=JST)
    existing_coupon = db.query(models.UserCoupon).filter(
        models.UserCoupon.user_id == current_user.id,
        models.UserCoupon.created_at >= today_start,
    ).first()
    
    if existing_coupon:
        return {
            "success": False,
            "message": "今日はすでにデイリークーポンを受け取りました",
            "next_available": "明日0時以降",
        }
    
    # ペルソナ装備チェック
    if not current_user.current_persona_id:
        return {
            "success": False,
            "message": "ペルソナを装備してからクーポンを受け取ってください",
        }
    
    # クーポンパラメータを計算
    params = calculate_coupon_params(db, current_user)
    
    # クーポン作成
    coupon = create_coupon(
        db=db,
        user=current_user,
        coupon_type=params["coupon_type"],
        discount_percent=params["discount_percent"],
        expires_hours=params["expires_hours"],
        issued_by_persona_id=current_user.current_persona_id,
    )
    
    db.commit()
    db.refresh(coupon)
    
    coupon_name = "送料割引" if params["coupon_type"] == "shipping_discount" else "ガチャ割引"
    
    return {
        "success": True,
        "message": f"🎫 {coupon_name} {params['discount_percent']}%OFFクーポンを獲得！",
        "coupon": {
            "id": coupon.id,
            "type": params["coupon_type"],
            "discount_percent": params["discount_percent"],
            "expires_at": coupon.expires_at.isoformat(),
            "expires_hours": params["expires_hours"],
        }
    }


# =============================================================================
# 初めての出品ボーナス
# =============================================================================

@router.post("/first-listing/claim")
def claim_first_listing(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """初めての出品ボーナスを受け取る (1回限り200pt)"""
    
    mission_key = "first_listing"
    
    if has_completed_mission(db, current_user.id, mission_key):
        return {"success": False, "message": "このミッションはすでに達成済みです"}
    
    # 出品があるか確認
    listing_count = db.query(models.Item).filter(
        models.Item.seller_id == current_user.firebase_uid
    ).count()
    
    if listing_count == 0:
        return {
            "success": False,
            "message": "まだ商品を出品していません。出品してからお戻りください！",
        }
    
    # 報酬付与
    reward = MISSION_REWARDS[mission_key]["gacha_points"]
    add_gacha_points(current_user, reward)
    complete_mission(db, current_user.id, mission_key)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎉 初出品ボーナス +{reward}ポイント獲得！",
        "reward": {"gacha_points": reward},
    }


# =============================================================================
# 初めての購入ボーナス
# =============================================================================

@router.post("/first-purchase/claim")
def claim_first_purchase(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """初めての購入ボーナスを受け取る (1回限り200pt)"""
    
    mission_key = "first_purchase"
    
    if has_completed_mission(db, current_user.id, mission_key):
        return {"success": False, "message": "このミッションはすでに達成済みです"}
    
    # 購入があるか確認
    purchase_count = db.query(models.Transaction).filter(
        models.Transaction.buyer_id == current_user.firebase_uid
    ).count()
    
    if purchase_count == 0:
        return {
            "success": False,
            "message": "まだ商品を購入していません。購入してからお戻りください！",
        }
    
    # 報酬付与
    reward = MISSION_REWARDS[mission_key]["gacha_points"]
    add_gacha_points(current_user, reward)
    complete_mission(db, current_user.id, mission_key)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎉 初購入ボーナス +{reward}ポイント獲得！",
        "reward": {"gacha_points": reward},
    }


# =============================================================================
# 連続ログイン3日ボーナス
# =============================================================================

@router.post("/login-streak/claim")
def claim_login_streak(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """連続ログイン3日ボーナスを受け取る (100pt + クーポン)"""
    
    mission_key = "login_streak_3"
    
    if has_completed_mission(db, current_user.id, mission_key):
        return {"success": False, "message": "このミッションはすでに達成済みです"}
    
    current_streak = current_user.login_streak or 0
    if current_streak < 3:
        return {
            "success": False,
            "message": f"連続ログインが3日未満です（現在: {current_streak}日）",
            "current_streak": current_streak,
        }
    
    # 報酬付与
    reward = MISSION_REWARDS[mission_key]["gacha_points"]
    add_gacha_points(current_user, reward)
    
    # ボーナスクーポンも発行
    create_coupon(
        db=db,
        user=current_user,
        coupon_type="gacha_discount",
        discount_percent=15,
        expires_hours=24,
    )
    
    complete_mission(db, current_user.id, mission_key)
    db.commit()
    
    return {
        "success": True,
        "message": f"🎉 連続ログイン3日達成！ +{reward}ポイント & ガチャ15%OFFクーポン獲得！",
        "reward": {
            "gacha_points": reward,
            "coupon": {"type": "gacha_discount", "discount_percent": 15, "expires_hours": 24},
        },
    }


# =============================================================================
# 週間いいね5回ボーナス
# =============================================================================

@router.post("/weekly-likes/claim")
def claim_weekly_likes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """週間いいね5回ボーナスを受け取る (30pt, 週1回リセット)"""
    
    now_jst = get_jst_now()
    
    # 今週すでに受け取っているか確認
    days_since = days_since_jst(current_user.last_weekly_likes_at)
    if days_since < 7:
        return {
            "success": False,
            "message": f"このミッションは週1回です（あと{7 - days_since}日でリセット）",
        }
    
    # 今週のいいね数を確認
    week_start = now_jst - timedelta(days=7)
    likes_this_week = db.query(models.Like).filter(
        models.Like.user_id == current_user.firebase_uid,
        models.Like.created_at >= week_start,
    ).count()
    
    if likes_this_week < 5:
        return {
            "success": False,
            "message": f"いいねが5回未満です（現在: {likes_this_week}回）",
            "current_likes": likes_this_week,
        }
    
    # 報酬付与
    reward = MISSION_REWARDS["weekly_likes"]["gacha_points"]
    add_gacha_points(current_user, reward)
    current_user.last_weekly_likes_at = now_jst
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎉 週間いいね達成！ +{reward}ポイント獲得！",
        "reward": {"gacha_points": reward},
    }


# =============================================================================
# 所持クーポン一覧
# =============================================================================

@router.get("/coupons")
def get_my_coupons(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """所持しているクーポン一覧（未使用のみ）"""
    
    now_jst = get_jst_now()
    
    coupons = db.query(models.UserCoupon).filter(
        models.UserCoupon.user_id == current_user.id,
        models.UserCoupon.used_at == None,
        models.UserCoupon.expires_at > now_jst,
    ).order_by(models.UserCoupon.expires_at.asc()).all()
    
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
    """現在のミッション状況を取得（全ミッション対応）"""
    
    now_jst = get_jst_now()
    today = now_jst.date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=JST)
    
    missions = []
    
    # 明日の0時を計算（クールタイム表示用）
    tomorrow_midnight = datetime.combine(today + timedelta(days=1), datetime.min.time()).replace(tzinfo=JST)
    
    # 1. デイリーログインボーナス
    daily_login_completed = is_same_day_jst(current_user.last_login_bonus_at)
    missions.append({
        "id": "daily_login",
        "name": "デイリーログインボーナス",
        "description": "毎日ログインしてポイントをゲット！",
        "completed": daily_login_completed,
        "claimable": not daily_login_completed,
        "reward": {"gacha_points": 50},
        "reset": "daily",
        "next_available_at": tomorrow_midnight.isoformat() if daily_login_completed else None,
    })
    
    # 2. デイリークーポン
    today_coupon = db.query(models.UserCoupon).filter(
        models.UserCoupon.user_id == current_user.id,
        models.UserCoupon.created_at >= today_start,
    ).first()
    
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
            params = calculate_coupon_params(db, current_user)
            expected_coupon = {
                "type": params["coupon_type"],
                "discount_percent": params["discount_percent"],
                "hours": params["expires_hours"],
            }
    
    missions.append({
        "id": "daily_coupon",
        "name": "デイリークーポン受取",
        "description": "装備中のペルソナに応じたクーポンがもらえます",
        "completed": today_coupon is not None,
        "claimable": today_coupon is None and current_user.current_persona_id is not None,
        "reward_preview": expected_coupon,
        "reset": "daily",
        "requires_persona": True,
        "next_available_at": tomorrow_midnight.isoformat() if today_coupon else None,
    })
    
    # 3. 初めての出品
    first_listing_done = has_completed_mission(db, current_user.id, "first_listing")
    listing_count = 0 if first_listing_done else db.query(models.Item).filter(
        models.Item.seller_id == current_user.firebase_uid
    ).count()
    
    missions.append({
        "id": "first_listing",
        "name": "初めての出品",
        "description": "商品を1点出品しよう！",
        "completed": first_listing_done,
        "claimable": not first_listing_done and listing_count > 0,
        "reward": {"gacha_points": 200},
        "reset": "once",
        "progress": {"current": min(listing_count, 1), "target": 1} if not first_listing_done else None,
    })
    
    # 4. 初めての購入
    first_purchase_done = has_completed_mission(db, current_user.id, "first_purchase")
    purchase_count = 0 if first_purchase_done else db.query(models.Transaction).filter(
        models.Transaction.buyer_id == current_user.firebase_uid
    ).count()
    
    missions.append({
        "id": "first_purchase",
        "name": "初めての購入",
        "description": "商品を1点購入しよう！",
        "completed": first_purchase_done,
        "claimable": not first_purchase_done and purchase_count > 0,
        "reward": {"gacha_points": 200},
        "reset": "once",
        "progress": {"current": min(purchase_count, 1), "target": 1} if not first_purchase_done else None,
    })
    
    # 5. 連続ログイン3日
    login_streak_done = has_completed_mission(db, current_user.id, "login_streak_3")
    current_streak = current_user.login_streak or 0
    
    missions.append({
        "id": "login_streak_3",
        "name": "連続ログイン3日",
        "description": "3日連続でログインしよう！",
        "completed": login_streak_done,
        "claimable": not login_streak_done and current_streak >= 3,
        "reward": {"gacha_points": 100, "coupon": "ガチャ15%OFF"},
        "reset": "once",
        "progress": {"current": min(current_streak, 3), "target": 3} if not login_streak_done else None,
    })
    
    # 6. 週間いいね5回
    weekly_likes_done = days_since_jst(current_user.last_weekly_likes_at) < 7
    
    week_start = now_jst - timedelta(days=7)
    likes_this_week = db.query(models.Like).filter(
        models.Like.user_id == current_user.firebase_uid,
        models.Like.created_at >= week_start,
    ).count()
    
    missions.append({
        "id": "weekly_likes",
        "name": "週間いいね5回",
        "description": "今週5回いいねしよう！",
        "completed": weekly_likes_done,
        "claimable": not weekly_likes_done and likes_this_week >= 5,
        "reward": {"gacha_points": 30},
        "reset": "weekly",
        "progress": {"current": min(likes_this_week, 5), "target": 5},
    })
    
    return {
        "missions": missions,
        "equipped_persona": equipped_persona,
        "memory_fragments": current_user.memory_fragments or 0,
        "gacha_points": current_user.gacha_points or 0,
        "login_streak": current_user.login_streak or 0,
        "total_login_days": current_user.total_login_days or 0,
    }
