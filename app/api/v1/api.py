from fastapi import APIRouter
from .endpoints import items, users, chat, gacha, search  # ★ searchを追加

api_router = APIRouter()

api_router.include_router(items.router, prefix="/items", tags=["Items"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(gacha.router, prefix="/gacha", tags=["Gacha"])
api_router.include_router(search.router, tags=["Search"])  # ★ searchを登録
