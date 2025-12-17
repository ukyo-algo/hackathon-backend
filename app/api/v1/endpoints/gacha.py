# hackathon-backend/app/api/v1/endpoints/gacha.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.gacha import GachaResponse
import random

from app.db.database import get_db
from app.api.v1.endpoints.users import get_current_user
from app.db import models
from app.schemas import user as user_schema

router = APIRouter()


"""Pydanticスキーマはapp/schemas/gacha.pyへ移動"""


@router.post("/draw", response_model=GachaResponse)
def draw_gacha(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    ガチャを引くエンドポイント。
    100ガチャポイント消費。
    """
    # 1. ガチャポイント消費ロジック
    GACHA_COST = 100
    if (current_user.gacha_points or 0) < GACHA_COST:
        raise HTTPException(
            status_code=400, 
            detail=f"ガチャポイントが足りません（必要: {GACHA_COST}ポイント、所持: {current_user.gacha_points or 0}ポイント）"
        )
    current_user.gacha_points = (current_user.gacha_points or 0) - GACHA_COST

    # 2. 排出ロジック (レアリティに基づく重み付け抽選)
    all_personas = db.query(models.AgentPersona).all()
    if not all_personas:
        raise HTTPException(status_code=500, detail="排出対象のキャラクターがいません")
    # --- GACHA_PROBABILITIESと同じ値をサーバー側にも定義 ---
    GACHA_PROBABILITIES = {
        1: 0.40,
        2: 0.30,
        3: 0.15,
        4: 0.10,
        5: 0.05,
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
    fragments_earned = 0

    # レアリティ別の記憶のかけら基本値
    DUPLICATE_FRAGMENTS = {
        1: 5,    # ノーマル被り → 5個
        2: 15,   # レア被り → 15個
        3: 30,   # スーパーレア被り → 30個
        4: 50,   # ウルトラレア被り → 50個
        5: 100,  # チャンピョン被り → 100個
    }

    if user_persona:
        # 既に持っている場合 -> スタック数を増やす & 記憶のかけら付与
        user_persona.stack_count += 1
        stack_count = user_persona.stack_count
        
        # 基本の記憶のかけら付与
        base_fragments = DUPLICATE_FRAGMENTS.get(drawn_persona.rarity, 5)
        
        # スキルボーナス計算（gacha_duplicate_fragments タイプのスキル）
        from app.db.data.personas import SKILL_DEFINITIONS
        skill_bonus = 0
        if current_user.current_persona_id:
            skill_def = SKILL_DEFINITIONS.get(current_user.current_persona_id)
            if skill_def and skill_def.get("skill_type") == "gacha_duplicate_fragments":
                # 現在のペルソナのレベルを取得
                current_up = db.query(models.UserPersona).filter(
                    models.UserPersona.user_id == current_user.id,
                    models.UserPersona.persona_id == current_user.current_persona_id,
                ).first()
                level = current_up.level if current_up else 1
                # Lv1で base_value、Lv10で max_value
                base_val = skill_def.get("base_value", 0)
                max_val = skill_def.get("max_value", 0)
                skill_bonus = base_val + int((max_val - base_val) * (level - 1) / 9)
        
        fragments_earned = base_fragments + skill_bonus
        current_user.memory_fragments = (current_user.memory_fragments or 0) + fragments_earned
        
        message = f"{drawn_persona.name}が被りました！(所持数: {stack_count}) 💎記憶のかけら +{fragments_earned}個！"
    else:
        # 新規入手
        new_up = models.UserPersona(
            user_id=current_user.id, persona_id=drawn_persona.id, stack_count=1
        )
        db.add(new_up)
        is_new = True
        message = f"やった！{drawn_persona.name}をゲットしました！"

    db.commit()

    # persona情報をPydanticモデルで返す（rarity_nameを追加）
    from app.schemas.user import PersonaBase

    persona_out = PersonaBase(
        id=drawn_persona.id,
        name=drawn_persona.name,
        avatar_url=drawn_persona.avatar_url,
        description=drawn_persona.description,
        theme_color=drawn_persona.theme_color,
        rarity=drawn_persona.rarity,
        rarity_name=drawn_persona.rarity_name,
    )
    return {
        "persona": persona_out,
        "is_new": is_new,
        "stack_count": stack_count,
        "message": message,
        "fragments_earned": fragments_earned,
        "total_memory_fragments": current_user.memory_fragments or 0,
    }
