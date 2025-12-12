# hackathon-backend/app/api/v1/endpoints/gacha.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import random

from app.db.database import get_db
from app.api.v1.endpoints.users import get_current_user
from app.db import models
from app.schemas import user as user_schema

router = APIRouter()


class GachaResponse(BaseModel):
    persona: user_schema.PersonaBase
    is_new: bool
    stack_count: int
    message: str


@router.post("/draw", response_model=GachaResponse)
def draw_gacha(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    ガチャを引くエンドポイント。
    現在は0コインで実行可能。
    """
    # 1. コイン消費ロジック (現在はスキップ)
    # if current_user.points < 100:
    #     raise HTTPException(status_code=400, detail="ポイントが足りません")
    # current_user.points -= 100

    # 2. 排出ロジック (レアリティに基づく重み付け抽選)
    all_personas = db.query(models.AgentPersona).all()
    if not all_personas:
        raise HTTPException(status_code=500, detail="排出対象のキャラクターがいません")

    # 重み付け: rarityが高いほど出にくい (例: rarity 1=100, 2=30, 3=10)
    # 簡易実装: rarity 1=60%, 2=30%, 3=10%
    weights = []
    for p in all_personas:
        if p.rarity == 1:
            weights.append(60)
        elif p.rarity == 2:
            weights.append(30)
        elif p.rarity == 3:
            weights.append(10)
        else:
            weights.append(10)  # default

    # 抽選実行
    drawn_persona = random.choices(all_personas, weights=weights, k=1)[0]

    # 3. ユーザーへの付与処理
    user_persona = (
        db.query(models.UserPersona)
        .filter(
            models.UserPersona.user_id == current_user.id,
            models.UserPersona.persona_id == drawn_persona.id,
        )
        .first()
    )

    is_new = False
    stack_count = 1

    if user_persona:
        # 既に持っている場合 -> スタック数を増やす
        user_persona.stack_count += 1
        stack_count = user_persona.stack_count
        message = f"{drawn_persona.name}が被りました！(所持数: {stack_count})"
    else:
        # 新規入手
        new_up = models.UserPersona(
            user_id=current_user.id, persona_id=drawn_persona.id, stack_count=1
        )
        db.add(new_up)
        is_new = True
        message = f"やった！{drawn_persona.name}をゲットしました！"

    db.commit()

    return {
        "persona": drawn_persona,
        "is_new": is_new,
        "stack_count": stack_count,
        "message": message,
    }
