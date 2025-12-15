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

    amount = getattr(settings, "REWARD_AMOUNT", 1000)
    cooldown_min = getattr(settings, "REWARD_COOLDOWN_MINUTES", 60)
    now = datetime.now(timezone.utc)

    # 直近クールダウン内のseeing_recommendイベントの有無で判定
    recent = (
        db.query(models.RewardEvent)
        .filter(
            models.RewardEvent.user_id == req.user_id,
            models.RewardEvent.kind == "seeing_recommend",
            models.RewardEvent.created_at >= now - timedelta(minutes=cooldown_min),
        )
        .first()
    )
    if recent:
        next_claim_at = (
            recent.created_at + timedelta(minutes=cooldown_min)
        ).astimezone(timezone.utc)
        return RewardClaimResponse(
            granted=False,
            amount=0,
            coins=user.coins or 0,
            next_claim_at=next_claim_at.isoformat(),
            reason="Cooldown not finished",
        )

    # 付与: 台帳に記録しつつ所持コインをインクリメント
    event = models.RewardEvent(
        user_id=req.user_id, kind="seeing_recommend", amount=amount
    )
    user.coins = (user.coins or 0) + amount
    db.add(event)
    db.add(user)
    db.commit()
    db.refresh(user)
    return RewardClaimResponse(
        granted=True,
        amount=amount,
        coins=user.coins,
        next_claim_at=(now + timedelta(minutes=cooldown_min)).isoformat(),
    )
