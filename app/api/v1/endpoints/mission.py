# hackathon-backend/app/api/v1/endpoints/mission.py
"""
ミッション＆デイリークーポンシステム（拡張版）
- デイリーログインボーナス
- デイリークーポン（既存）
- 初出品ボーナス
- 初購入ボーナス
- 連続ログインボーナス
- 週間いいねボーナス
"""

from datetime import datetime, timedelta, timezone, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from typing import Optional

from app.db.database import get_db
from app.db import models
from app.api.v1.endpoints.users import get_current_user
from app.db.data.personas import SKILL_DEFINITIONS


router = APIRouter()

# ミッション報酬定義
MISSION_REWARDS = {
    "daily_login": {"gacha_points": 50, "description": "デイリーログインボーナス"},
    "first_listing": {"gacha_points": 200, "description": "初めての出品"},
    "first_purchase": {"gacha_points": 200, "description": "初めての購入"},
    "login_streak_3": {"gacha_points": 100, "description": "連続ログイン3日達成"},
    "weekly_likes": {"gacha_points": 30, "description": "週間いいね5回達成"},
}


# =============================================================================
# ヘルパー関数
# =============================================================================

def get_jst_now():
    """日本時間の現在時刻を取得"""
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    return datetime.now(jst)


def get_jst_today():
    """日本時間の今日の日付を取得"""
    return get_jst_now().date()


def is_same_day_jst(dt1, dt2=None):
    """2つの日時が同じ日（JST）かどうか"""
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    
    if dt2 is None:
        dt2 = get_jst_now()
    
    if dt1 is None:
        return False
    
    # タイムゾーン情報があれば変換
    if dt1.tzinfo is not None:
        dt1_jst = dt1.astimezone(jst)
    else:
        dt1_jst = jst.localize(dt1)
    
    if isinstance(dt2, datetime):
        if dt2.tzinfo is not None:
            dt2_jst = dt2.astimezone(jst)
        else:
            dt2_jst = jst.localize(dt2)
    else:
        dt2_jst = dt2  # dateオブジェクトの場合
    
    return dt1_jst.date() == (dt2_jst.date() if isinstance(dt2_jst, datetime) else dt2_jst)


def is_consecutive_day_jst(last_dt):
    """前回が昨日かどうか（連続ログイン判定用）"""
    if last_dt is None:
        return False
    
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    
    if last_dt.tzinfo is not None:
        last_jst = last_dt.astimezone(jst)
    else:
        last_jst = jst.localize(last_dt)
    
    today = get_jst_today()
    yesterday = today - timedelta(days=1)
    
    return last_jst.date() == yesterday


def has_completed_mission(db: Session, user_id: int, mission_key: str) -> bool:
    """ワンタイムミッション達成済みかどうか"""
    return db.query(models.UserMission).filter(
        models.UserMission.user_id == user_id,
        models.UserMission.mission_key == mission_key,
    ).first() is not None


def complete_mission(db: Session, user_id: int, mission_key: str):
    """ワンタイムミッション達成を記録"""
    mission = models.UserMission(
        user_id=user_id,
        mission_key=mission_key,
    )
    db.add(mission)


# =============================================================================
# デイリーログインボーナス
# =============================================================================

@router.post("/daily-login/claim")
def claim_daily_login(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    デイリーログインボーナスを受け取る
    - 1日1回50ガチャポイント
    - 連続ログイン日数をカウント
    """
    now_jst = get_jst_now()
    
    # 今日すでに受け取っているか確認
    if is_same_day_jst(current_user.last_login_bonus_at):
        return {
            "success": False,
            "message": "今日はすでにログインボーナスを受け取りました",
            "next_available": "明日0時以降",
        }
    
    # 連続ログイン判定
    if is_consecutive_day_jst(current_user.last_login_bonus_at):
        # 昨日もログインしていた → 連続ログイン継続
        current_user.login_streak = (current_user.login_streak or 0) + 1
    else:
        # 連続が途切れた → リセット
        current_user.login_streak = 1
    
    # 累計ログイン日数
    current_user.total_login_days = (current_user.total_login_days or 0) + 1
    
    # ログインボーナス付与
    reward = MISSION_REWARDS["daily_login"]["gacha_points"]
    current_user.gacha_points = (current_user.gacha_points or 0) + reward
    current_user.last_login_bonus_at = now_jst
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎫 ログインボーナス +{reward}ポイント獲得！",
        "reward": {
            "gacha_points": reward,
        },
        "login_streak": current_user.login_streak,
        "total_login_days": current_user.total_login_days,
    }


# =============================================================================
# デイリークーポン受け取り（既存）
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
    now_jst = get_jst_now()
    today = now_jst.date()
    
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    
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
# 初めての出品ボーナス
# =============================================================================

@router.post("/first-listing/claim")
def claim_first_listing(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    初めての出品ボーナスを受け取る
    - 1回限り200ガチャポイント
    """
    mission_key = "first_listing"
    
    # すでに達成済みか確認
    if has_completed_mission(db, current_user.id, mission_key):
        return {
            "success": False,
            "message": "このミッションはすでに達成済みです",
        }
    
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
    current_user.gacha_points = (current_user.gacha_points or 0) + reward
    complete_mission(db, current_user.id, mission_key)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎉 初出品ボーナス +{reward}ポイント獲得！",
        "reward": {
            "gacha_points": reward,
        }
    }


# =============================================================================
# 初めての購入ボーナス
# =============================================================================

@router.post("/first-purchase/claim")
def claim_first_purchase(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    初めての購入ボーナスを受け取る
    - 1回限り200ガチャポイント
    """
    mission_key = "first_purchase"
    
    # すでに達成済みか確認
    if has_completed_mission(db, current_user.id, mission_key):
        return {
            "success": False,
            "message": "このミッションはすでに達成済みです",
        }
    
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
    current_user.gacha_points = (current_user.gacha_points or 0) + reward
    complete_mission(db, current_user.id, mission_key)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎉 初購入ボーナス +{reward}ポイント獲得！",
        "reward": {
            "gacha_points": reward,
        }
    }


# =============================================================================
# 連続ログイン3日ボーナス
# =============================================================================

@router.post("/login-streak/claim")
def claim_login_streak(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    連続ログイン3日ボーナスを受け取る
    - 100ガチャポイント + クーポン
    """
    mission_key = "login_streak_3"
    
    # すでに達成済みか確認
    if has_completed_mission(db, current_user.id, mission_key):
        return {
            "success": False,
            "message": "このミッションはすでに達成済みです",
        }
    
    # 連続ログイン日数確認
    if (current_user.login_streak or 0) < 3:
        return {
            "success": False,
            "message": f"連続ログインが3日未満です（現在: {current_user.login_streak or 0}日）",
            "current_streak": current_user.login_streak or 0,
        }
    
    # 報酬付与
    reward = MISSION_REWARDS[mission_key]["gacha_points"]
    current_user.gacha_points = (current_user.gacha_points or 0) + reward
    
    # ボーナスクーポンも発行
    now_jst = get_jst_now()
    bonus_coupon = models.UserCoupon(
        user_id=current_user.id,
        coupon_type="gacha_discount",
        discount_percent=15,
        expires_at=now_jst + timedelta(hours=24),
        issued_by_persona_id=None,
    )
    db.add(bonus_coupon)
    
    complete_mission(db, current_user.id, mission_key)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎉 連続ログイン3日達成！ +{reward}ポイント & ガチャ15%OFFクーポン獲得！",
        "reward": {
            "gacha_points": reward,
            "coupon": {
                "type": "gacha_discount",
                "discount_percent": 15,
                "expires_hours": 24,
            }
        }
    }


# =============================================================================
# 週間いいね5回ボーナス
# =============================================================================

@router.post("/weekly-likes/claim")
def claim_weekly_likes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    週間いいね5回ボーナスを受け取る
    - 30ガチャポイント（週1回リセット）
    """
    now_jst = get_jst_now()
    
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    
    # 今週すでに受け取っているか確認（7日以内）
    if current_user.last_weekly_likes_at:
        if current_user.last_weekly_likes_at.tzinfo:
            last_at = current_user.last_weekly_likes_at.astimezone(jst)
        else:
            last_at = jst.localize(current_user.last_weekly_likes_at)
        
        days_since = (now_jst - last_at).days
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
    current_user.gacha_points = (current_user.gacha_points or 0) + reward
    current_user.last_weekly_likes_at = now_jst
    
    db.commit()
    
    return {
        "success": True,
        "message": f"🎉 週間いいね達成！ +{reward}ポイント獲得！",
        "reward": {
            "gacha_points": reward,
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
    now_jst = get_jst_now()
    
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
# ミッション一覧（拡張版）
# =============================================================================

@router.get("/missions")
def get_missions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    現在のミッション状況を取得（全ミッション対応）
    """
    now_jst = get_jst_now()
    today = now_jst.date()
    
    from pytz import timezone as tz
    jst = tz('Asia/Tokyo')
    
    missions = []
    
    # ----------------------------------------------------------------
    # 1. デイリーログインボーナス
    # ----------------------------------------------------------------
    daily_login_completed = is_same_day_jst(current_user.last_login_bonus_at)
    missions.append({
        "id": "daily_login",
        "name": "デイリーログインボーナス",
        "description": "毎日ログインしてポイントをゲット！",
        "completed": daily_login_completed,
        "claimable": not daily_login_completed,
        "reward": {"gacha_points": 50},
        "reset": "daily",
    })
    
    # ----------------------------------------------------------------
    # 2. デイリークーポン
    # ----------------------------------------------------------------
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
    
    missions.append({
        "id": "daily_coupon",
        "name": "デイリークーポン受取",
        "description": "装備中のペルソナに応じたクーポンがもらえます",
        "completed": today_coupon is not None,
        "claimable": today_coupon is None and current_user.current_persona_id is not None,
        "reward_preview": expected_coupon,
        "reset": "daily",
        "requires_persona": True,
    })
    
    # ----------------------------------------------------------------
    # 3. 初めての出品
    # ----------------------------------------------------------------
    first_listing_done = has_completed_mission(db, current_user.id, "first_listing")
    listing_count = db.query(models.Item).filter(
        models.Item.seller_id == current_user.firebase_uid
    ).count() if not first_listing_done else 0
    
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
    
    # ----------------------------------------------------------------
    # 4. 初めての購入
    # ----------------------------------------------------------------
    first_purchase_done = has_completed_mission(db, current_user.id, "first_purchase")
    purchase_count = db.query(models.Transaction).filter(
        models.Transaction.buyer_id == current_user.firebase_uid
    ).count() if not first_purchase_done else 0
    
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
    
    # ----------------------------------------------------------------
    # 5. 連続ログイン3日
    # ----------------------------------------------------------------
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
    
    # ----------------------------------------------------------------
    # 6. 週間いいね5回
    # ----------------------------------------------------------------
    weekly_likes_done = False
    if current_user.last_weekly_likes_at:
        if current_user.last_weekly_likes_at.tzinfo:
            last_at = current_user.last_weekly_likes_at.astimezone(jst)
        else:
            last_at = jst.localize(current_user.last_weekly_likes_at)
        days_since = (now_jst - last_at).days
        weekly_likes_done = days_since < 7
    
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
