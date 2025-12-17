from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.db.database import get_db
from app.schemas.reward import RewardClaimRequest, RewardClaimResponse


router = APIRouter()


@router.post("/claim/seeing_recommend", response_model=RewardClaimResponse)
def claim_seeing_recommend_reward(
    req: RewardClaimRequest, db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.firebase_uid == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base_amount = getattr(settings, "REWARD_AMOUNT", 100)  # 基本100ポイント
    cooldown_min = getattr(settings, "REWARD_COOLDOWN_MINUTES", 60)  # 基本60分
    now = datetime.now(timezone.utc)
    
    # スキルボーナス計算
    from app.db.data.personas import SKILL_DEFINITIONS
    quest_bonus = 0
    cooldown_reduction = 0
    
    if user.current_persona_id:
        skill_def = SKILL_DEFINITIONS.get(user.current_persona_id)
        if skill_def:
            # 現在のペルソナのレベルを取得
            current_up = db.query(models.UserPersona).filter(
                models.UserPersona.user_id == user.id,
                models.UserPersona.persona_id == user.current_persona_id,
            ).first()
            level = current_up.level if current_up else 1
            
            # quest_reward_bonus: クエスト報酬UP
            if skill_def.get("skill_type") == "quest_reward_bonus":
                base_val = skill_def.get("base_value", 0)
                max_val = skill_def.get("max_value", 0)
                quest_bonus = base_val + int((max_val - base_val) * (level - 1) / 9)
            
            # quest_cooldown_reduction: クールダウン短縮（分）
            if skill_def.get("skill_type") == "quest_cooldown_reduction":
                base_val = skill_def.get("base_value", 0)
                max_val = skill_def.get("max_value", 0)
                cooldown_reduction = base_val + int((max_val - base_val) * (level - 1) / 9)
    
    # 実際のクールダウン時間
    actual_cooldown = max(cooldown_min - cooldown_reduction, 5)  # 最小5分
    
    # 直近クールダウン内のseeing_recommendイベントの有無で判定
    recent = (
        db.query(models.RewardEvent)
        .filter(
            models.RewardEvent.user_id == req.user_id,
            models.RewardEvent.kind == "seeing_recommend",
            models.RewardEvent.created_at >= now - timedelta(minutes=actual_cooldown),
        )
        .first()
    )
    if recent:
        next_claim_at = (
            recent.created_at + timedelta(minutes=actual_cooldown)
        ).astimezone(timezone.utc)
        return RewardClaimResponse(
            granted=False,
            amount=0,
            gacha_points=user.gacha_points or 0,
            next_claim_at=next_claim_at.isoformat(),
            reason="Cooldown not finished",
        )

    # 最終報酬
    final_amount = base_amount + quest_bonus
    
    # 付与: 台帳に記録しつつ所持ポイントをインクリメント
    event = models.RewardEvent(
        user_id=req.user_id, kind="seeing_recommend", amount=final_amount
    )
    user.gacha_points = (user.gacha_points or 0) + final_amount
    db.add(event)
    db.add(user)
    db.commit()
    db.refresh(user)
    return RewardClaimResponse(
        granted=True,
        amount=final_amount,
        gacha_points=user.gacha_points,
        next_claim_at=(now + timedelta(minutes=actual_cooldown)).isoformat(),
    )
