RARITY_LABELS = {
    1: "ノーマル",
    2: "レア",
    3: "スーパーレア",
    4: "ウルトラレア",
    5: "チャンピョン",
}
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

    # --- GACHA_PROBABILITIESと同じ値をサーバー側にも定義 ---
    GACHA_PROBABILITIES = {
        1: 0.60,  # 60%
        2: 0.20,  # 20%
        3: 0.10,  # 10%
        4: 0.07,  # 7%
        5: 0.03,  # 3%
    }

    # レアリティごとの候補リストを作成
    rarity_to_personas = {}
    for p in all_personas:
        rarity_to_personas.setdefault(p.rarity, []).append(p)

    # 確率リストとレアリティリストを作成
    rarities = list(GACHA_PROBABILITIES.keys())
    probabilities = [GACHA_PROBABILITIES[r] for r in rarities]

    # まずレアリティを抽選
    drawn_rarity = random.choices(rarities, weights=probabilities, k=1)[0]
    # そのレアリティの中からランダムに1つ選ぶ
    drawn_persona = random.choice(rarity_to_personas[drawn_rarity])

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
        "rarity_label": RARITY_LABELS.get(drawn_persona.rarity, ""),
    }
