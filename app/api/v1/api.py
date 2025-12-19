from fastapi import APIRouter
from .endpoints import (
    items,
    users,
    chat,
    gacha,
    search,
    transactions,
    llm,
    recommend,
    rewards,
    mission,
    notification,
)  # LLM/Reco追加

api_router = APIRouter()

api_router.include_router(items.router, prefix="/items", tags=["Items"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(gacha.router, prefix="/gacha", tags=["Gacha"])
api_router.include_router(search.router, tags=["Search"])  # ★ searchを登録
api_router.include_router(
    transactions.router, prefix="/transactions", tags=["Transactions"]
)  # 取引
api_router.include_router(llm.router, prefix="/llm", tags=["LLM"])
api_router.include_router(
    recommend.router,
    prefix="/recommend",
    tags=["Recommendations"],
)
api_router.include_router(
    rewards.router,
    prefix="/rewards",
    tags=["Rewards"],
)
api_router.include_router(
    mission.router,
    prefix="/mission",
    tags=["Mission"],
)
api_router.include_router(
    notification.router,
    tags=["Notifications"],
)
