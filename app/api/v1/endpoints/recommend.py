from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.db.database import get_db
from app.db import models
from app.services.llm_service import get_llm_service
from app.schemas.recommend import (
    RecommendRequest,
    RecommendResponse,
    RecommendItem,
    RecommendHistoryItem,
)


router = APIRouter()


@router.post("", response_model=RecommendResponse)
def recommend(req: RecommendRequest, db: Session = Depends(get_db)):
    """
    AIがおすすめ商品を生成し、DBに保存する。
    """
    llm = get_llm_service(db)
    if req.mode not in ("history", "keyword"):
        raise HTTPException(
            status_code=400, detail="mode must be 'history' or 'keyword'"
        )
    result = llm.generate_recommendations(
        user_id=req.user_id, mode=req.mode, keyword=req.keyword
    )

    # 型合わせ（最大4件に制限）
    items = [RecommendItem(**i) for i in result.get("items", [])][:4]
    reasons = result.get("reasons", {})

    # --- DBに保存 ---
    for item in items:
        rec = models.LLMRecommendation(
            user_id=req.user_id,
            item_id=item.item_id,
            reason=reasons.get(item.item_id),
        )
        db.add(rec)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[recommend] DB save failed: {e}")

    return RecommendResponse(
        can_recommend=result.get("can_recommend", False),
        persona_question=result.get("persona_question", ""),
        message=result.get("message", ""),
        items=items,
        persona=result.get("persona", {}),
        reason=result.get("reason"),
    )


@router.get("/history", response_model=List[RecommendHistoryItem])
def get_recommend_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    x_firebase_uid: str = Header(...),
):
    """
    ユーザーのおすすめ履歴を取得（新しい順）。
    """
    recs = (
        db.query(models.LLMRecommendation)
        .options(joinedload(models.LLMRecommendation.item))
        .filter(models.LLMRecommendation.user_id == x_firebase_uid)
        .order_by(models.LLMRecommendation.recommended_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for rec in recs:
        if rec.item:  # アイテムが存在する場合のみ
            result.append(
                RecommendHistoryItem(
                    id=rec.id,
                    item_id=rec.item_id,
                    name=rec.item.name,
                    price=rec.item.price,
                    image_url=rec.item.image_url,
                    reason=rec.reason,
                    interest=rec.interest,
                    recommended_at=rec.recommended_at.isoformat() if rec.recommended_at else "",
                )
            )
    return result


@router.put("/{recommendation_id}/interest")
def update_interest(
    recommendation_id: int,
    interest: str,  # "interested" or "not_interested"
    db: Session = Depends(get_db),
    x_firebase_uid: str = Header(...),
):
    """
    おすすめ履歴の興味あり/なしを更新。
    """
    rec = (
        db.query(models.LLMRecommendation)
        .filter(
            models.LLMRecommendation.id == recommendation_id,
            models.LLMRecommendation.user_id == x_firebase_uid,
        )
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if interest not in ("interested", "not_interested", None):
        raise HTTPException(status_code=400, detail="Invalid interest value")

    rec.interest = interest
    db.commit()
    return {"status": "ok", "interest": interest}
