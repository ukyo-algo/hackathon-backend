from fastapi import APIRouter
from .endpoints import items, users, chat  # ★ chatを追加

api_router = APIRouter()

api_router.include_router(items.router, prefix="/items", tags=["Items"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
# ★ 追加
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
