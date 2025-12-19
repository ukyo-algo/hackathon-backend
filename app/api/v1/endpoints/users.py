# hackathon-backend/app/api/v1/endpoints/users.py

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Header,  # ↓↓↓ 追加: ヘッダーを取得するために必要
)
from sqlalchemy.orm import Session  # Sessionは必須

from app.db.database import get_db
from app.db import models
from app.schemas import user as user_schema

from typing import List
from sqlalchemy.orm import joinedload
from app.schemas import item as item_schema
from app.schemas import transaction as transaction_schema

router = APIRouter()


def get_current_user(
    db: Session = Depends(get_db),
    # フロントエンドから "X-Firebase-Uid" というヘッダーでUIDを受け取る
    x_firebase_uid: str | None = Header(default=None),
):
    """
    リクエストヘッダーのUIDを元に、現在のユーザーを特定する。
    """
    if x_firebase_uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証情報(X-Firebase-Uid)が不足しています",
        )

    # DBからユーザーを検索
    user = (
        db.query(models.User).filter(models.User.firebase_uid == x_firebase_uid).first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません。先に登録してください。",
        )
    return user


@router.get("/personas", response_model=List[user_schema.PersonaBase])
def read_all_personas(db: Session = Depends(get_db)):
    """
    全キャラクターのリストを取得します。
    """
    personas = db.query(models.AgentPersona).all()
    return [user_schema.PersonaBase.model_validate(p) for p in personas]


@router.get("/me", response_model=user_schema.UserBase)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """
    現在のユーザー情報を取得します。
    """
    return current_user


@router.post("/", response_model=user_schema.UserBase)
def create_user(user: user_schema.UserCreate, db: Session = Depends(get_db)):
    """
    新規ユーザーをデータベースに登録します。すでに存在する場合は既存のユーザー情報を返します。
    """
    # すでに登録済みかチェック
    db_user = (
        db.query(models.User)
        .filter(models.User.firebase_uid == user.firebase_uid)
        .first()
    )
    if db_user:  # すでに存在する場合はそのまま返す
        return db_user

    # 1. デフォルトキャラ(ID:1)を取得
    default_persona = (
        db.query(models.AgentPersona).filter(models.AgentPersona.id == 1).first()
    )

    new_user = models.User(
        firebase_uid=user.firebase_uid,
        username=user.username,
        email=user.email,
        icon_url=user.icon_url,
        current_persona_id=1 if default_persona else None,  # 最初から装備
        gacha_points=2000,  # 初期ポイント: 2000pt
    )

    # ★重要: 「所持リスト」にも追加
    if default_persona:
        # new_user.owned_personas.append(default_persona)
        # ↑ 中間テーブルクラス化に伴い、直接appendできなくなったため修正
        # まずユーザーを保存してIDを確定させる
        db.add(new_user)
        db.flush()

        # 中間テーブルレコードを作成
        user_persona = models.UserPersona(
            user_id=new_user.id, persona_id=default_persona.id, stack_count=1
        )
        db.add(user_persona)

    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/me/items", response_model=List[item_schema.Item])
def read_own_items(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が「出品」した商品の一覧を取得
    """
    items = (
        db.query(models.Item)
        .options(joinedload(models.Item.seller))  # N+1対策
        .filter(models.Item.seller_id == current_user.firebase_uid)
        .order_by(models.Item.created_at.desc())
        .all()
    )
    return items


@router.get("/me/transactions", response_model=List[transaction_schema.Transaction])
def read_own_transactions(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が「購入」した履歴を取得（商品情報付き）
    """
    transactions = (
        db.query(models.Transaction)
        .options(joinedload(models.Transaction.item))  # 商品情報も一緒に取得
        .filter(models.Transaction.buyer_id == current_user.firebase_uid)
        .order_by(models.Transaction.created_at.desc())
        .all()
    )
    return transactions


@router.get("/me/likes", response_model=List[item_schema.Item])
def read_own_likes(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が「いいね」した商品の一覧を取得
    """
    liked_items = (
        db.query(models.Item)
        .join(models.Like, models.Item.item_id == models.Like.item_id)
        .options(joinedload(models.Item.seller))  # N+1対策
        .filter(models.Like.user_id == current_user.firebase_uid)
        .order_by(models.Like.created_at.desc())
        .all()
    )
    return liked_items


@router.get("/me/comments", response_model=List[item_schema.Item])
def read_own_commented_items(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が「コメント」した商品の一覧を取得
    """
    commented_items = (
        db.query(models.Item)
        .join(models.Comment, models.Item.item_id == models.Comment.item_id)
        .options(joinedload(models.Item.seller))  # N+1対策
        .filter(models.Comment.user_id == current_user.firebase_uid)
        .order_by(models.Comment.created_at.desc())
        .all()
    )
    return commented_items


# app/api/v1/endpoints/users.py に以下を追加


@router.put("/me/persona", response_model=user_schema.UserBase)
def update_user_persona(
    persona_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    現在のユーザーのAIアシスタントキャラクターを更新します。
    """
    # 指定されたpersona_idがユーザーの所持リストにあるか確認
    # 中間テーブル(UserPersona)を介してチェック
    user_persona = (
        db.query(models.UserPersona)
        .filter(
            models.UserPersona.user_id == current_user.id,
            models.UserPersona.persona_id == persona_id,
        )
        .first()
    )

    if not user_persona:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指定されたキャラクターは所持していません。",
        )
    # ユーザーのcurrent_persona_idを更新
    current_user.current_persona_id = persona_id
    db.commit()
    db.refresh(current_user)

    return current_user


@router.get("/me/personas")
def read_own_personas(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """
    自分が所持しているAIアシスタントキャラクターの一覧を取得（レベル情報付き）
    """
    from app.db.data.personas import get_dynamic_skill_text
    
    # 中間テーブル経由でPersonaとレベル情報を取得
    user_personas = (
        db.query(models.UserPersona, models.AgentPersona)
        .join(models.AgentPersona, models.AgentPersona.id == models.UserPersona.persona_id)
        .filter(models.UserPersona.user_id == current_user.id)
        .all()
    )
    
    results = []
    for user_persona, persona in user_personas:
        persona_dict = user_schema.PersonaBase.model_validate(persona).model_dump()
        # レベルに基づいた動的スキルテキストを設定
        persona_dict["level"] = user_persona.level
        persona_dict["stack_count"] = user_persona.stack_count
        persona_dict["skill_effect"] = get_dynamic_skill_text(persona.id, user_persona.level)
        results.append(persona_dict)
    
    return results


# レアリティ別レベルアップコスト（記憶のかけら）
LEVEL_UP_COSTS = {
    # (rarity, current_level) -> cost
    1: [5, 10, 15, 20, 30, 40, 50, 60, 70],   # ノーマル: 合計300
    2: [10, 20, 30, 40, 60, 80, 100, 120, 140],  # レア: 合計600
    3: [15, 30, 45, 60, 90, 120, 150, 180, 210],  # スーパーレア: 合計900
    4: [20, 40, 60, 80, 120, 160, 200, 240, 280],  # ウルトラレア: 合計1200
    5: [30, 60, 90, 120, 180, 240, 300, 360, 420],  # チャンピョン: 合計1800
}


@router.post("/me/personas/{persona_id}/levelup")
def level_up_persona(
    persona_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    指定したペルソナをレベルアップする（記憶のかけらを消費）
    """
    # 1. 所持しているか確認
    user_persona = (
        db.query(models.UserPersona)
        .filter(
            models.UserPersona.user_id == current_user.id,
            models.UserPersona.persona_id == persona_id,
        )
        .first()
    )
    if not user_persona:
        raise HTTPException(
            status_code=400,
            detail="このペルソナを所持していません",
        )
    
    # 2. レベル上限チェック
    MAX_LEVEL = 10
    if user_persona.level >= MAX_LEVEL:
        raise HTTPException(
            status_code=400,
            detail=f"このペルソナは最高レベル（{MAX_LEVEL}）に達しています",
        )
    
    # 3. ペルソナのレアリティを取得
    persona = db.query(models.AgentPersona).filter(models.AgentPersona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="ペルソナが見つかりません")
    
    # 4. 必要な記憶のかけらを計算（レベルアップ必要数減少スキル考慮）
    from app.db.data.personas import SKILL_DEFINITIONS
    
    base_cost = LEVEL_UP_COSTS.get(persona.rarity, LEVEL_UP_COSTS[1])[user_persona.level - 1]
    
    # levelup_cost_reduction スキルの適用
    cost_reduction_percent = 0
    if current_user.current_persona_id:
        skill_def = SKILL_DEFINITIONS.get(current_user.current_persona_id)
        if skill_def and skill_def.get("skill_type") == "levelup_cost_reduction":
            current_up = db.query(models.UserPersona).filter(
                models.UserPersona.user_id == current_user.id,
                models.UserPersona.persona_id == current_user.current_persona_id,
            ).first()
            level = current_up.level if current_up else 1
            base_val = skill_def.get("base_value", 0)
            max_val = skill_def.get("max_value", 0)
            cost_reduction_percent = base_val + int((max_val - base_val) * (level - 1) / 9)
    
    actual_cost = base_cost - (base_cost * cost_reduction_percent // 100)
    actual_cost = max(actual_cost, 1)  # 最低1
    
    # 5. 記憶のかけら残高チェック
    if (current_user.memory_fragments or 0) < actual_cost:
        raise HTTPException(
            status_code=400,
            detail=f"記憶のかけらが足りません（必要: {actual_cost}個、所持: {current_user.memory_fragments or 0}個）",
        )
    
    # 6. レベルアップ実行
    current_user.memory_fragments = (current_user.memory_fragments or 0) - actual_cost
    user_persona.level += 1
    
    db.commit()
    db.refresh(user_persona)
    db.refresh(current_user)
    
    return {
        "success": True,
        "persona_id": persona_id,
        "new_level": user_persona.level,
        "fragments_spent": actual_cost,
        "remaining_fragments": current_user.memory_fragments,
    }




@router.post("/me/add-fragments")
def add_memory_fragments(
    request: user_schema.AddFragmentsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    記憶のかけらを追加する（購入処理）
    """
    amount = request.amount
    
    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="追加する量は正の数である必要があります",
        )
    
    current_user.memory_fragments = (current_user.memory_fragments or 0) + amount
    db.commit()
    db.refresh(current_user)
    
    return {
        "success": True,
        "added_fragments": amount,
        "current_fragments": current_user.memory_fragments,
        "message": f"💎 記憶のかけら +{amount}個 を追加しました！",
    }





@router.post("/me/subscribe")
def purchase_subscription(
    request: user_schema.SubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    月額パスを購入する（¥500/月）
    デュアルペルソナ機能が有効になる
    """
    from datetime import datetime, timedelta
    
    months = request.months
    if months <= 0:
        raise HTTPException(status_code=400, detail="購入月数は1以上である必要があります")
    
    # 既存のサブスクがあれば延長、なければ今日から開始
    now = datetime.now()
    if current_user.subscription_expires_at and current_user.subscription_expires_at > now:
        new_expiry = current_user.subscription_expires_at + timedelta(days=30 * months)
    else:
        new_expiry = now + timedelta(days=30 * months)
    
    current_user.subscription_tier = "monthly"
    current_user.subscription_expires_at = new_expiry
    db.commit()
    db.refresh(current_user)
    
    return {
        "success": True,
        "subscription_tier": "monthly",
        "expires_at": new_expiry.isoformat(),
        "message": f"🎉 月額パス（{months}ヶ月）を購入しました！デュアルペルソナ機能が有効になりました！",
    }





@router.post("/me/sub-persona")
def set_sub_persona(
    request: user_schema.SetSubPersonaRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    サブペルソナを設定する（月額パス加入者のみ）
    """
    from datetime import datetime
    
    print(f"[set_sub_persona] START - user_id={current_user.id}, persona_id={request.persona_id}")
    print(f"[set_sub_persona] subscription_tier={current_user.subscription_tier}, expires_at={current_user.subscription_expires_at}")
    
    # サブスク確認
    now = datetime.now()
    if current_user.subscription_tier != "monthly" or \
       not current_user.subscription_expires_at or \
       current_user.subscription_expires_at < now:
        print(f"[set_sub_persona] ERROR - subscription invalid")
        raise HTTPException(
            status_code=403,
            detail="サブペルソナを設定するには月額パスが必要です",
        )
    
    persona_id = request.persona_id
    
    # 所持しているか確認
    owned_ids = [up.persona_id for up in current_user.owned_personas_association]
    print(f"[set_sub_persona] owned_ids={owned_ids}")
    if persona_id not in owned_ids:
        print(f"[set_sub_persona] ERROR - persona not owned")
        raise HTTPException(
            status_code=400,
            detail="所持していないペルソナは設定できません",
        )
    
    # メインと同じペルソナは設定不可
    if persona_id == current_user.current_persona_id:
        print(f"[set_sub_persona] ERROR - same as main persona")
        raise HTTPException(
            status_code=400,
            detail="メインペルソナと同じキャラクターはサブに設定できません",
        )
    
    current_user.sub_persona_id = persona_id
    db.commit()
    db.refresh(current_user)
    
    print(f"[set_sub_persona] SUCCESS - sub_persona_id set to {persona_id}")
    
    # サブペルソナ情報を取得
    sub_persona = db.query(models.AgentPersona).filter(models.AgentPersona.id == persona_id).first()
    
    return {
        "success": True,
        "sub_persona_id": persona_id,
        "sub_persona_name": sub_persona.name if sub_persona else None,
        "message": f"🎭 サブペルソナを設定しました！",
    }


@router.delete("/me/sub-persona")
def unset_sub_persona(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    サブペルソナを解除する
    """
    current_user.sub_persona_id = None
    db.commit()
    
    return {
        "success": True,
        "message": "サブペルソナを解除しました",
    }
