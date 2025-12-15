from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.db.database import get_db

router = APIRouter()


@router.get("")
def get_recommendations(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    LLMによるおすすめのスケルトン。現段階では固定の簡易返却と報酬付与情報のみ。
    実装後はユーザー・ペルソナ・履歴に応じて生成し、coins付与をトランザクションで処理予定。
    """
    items = [
        {"name": "おすすめA", "reason": "最近の閲覧傾向にマッチ"},
        {"name": "おすすめB", "reason": "価格と状態のバランスが良い"},
    ]
    reward = {"coins": 5}
    return {"items": items, "reward": reward}
