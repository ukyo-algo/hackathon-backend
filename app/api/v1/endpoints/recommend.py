from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.llm_service import get_llm_service
from app.schemas.recommend import RecommendRequest, RecommendResponse, RecommendItem


router = APIRouter()


@router.post("", response_model=RecommendResponse)
def recommend(req: RecommendRequest, db: Session = Depends(get_db)):
    llm = get_llm_service(db)
    if req.mode not in ("history", "keyword"):
        raise HTTPException(
            status_code=400, detail="mode must be 'history' or 'keyword'"
        )
    result = llm.generate_recommendations(
        user_id=req.user_id, mode=req.mode, keyword=req.keyword
    )

    # 型合わせ
    items = [RecommendItem(**i) for i in result.get("items", [])]
    return RecommendResponse(
        can_recommend=result.get("can_recommend", False),
        persona_question=result.get("persona_question", ""),
        items=items,
        persona=result.get("persona", {}),
        reason=result.get("reason"),
    )
