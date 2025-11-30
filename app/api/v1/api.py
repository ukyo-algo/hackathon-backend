from fastapi import APIRouter
from .endpoints import items, users  # usersを追加

api_router = APIRouter()

api_router.include_router(items.router, prefix="/items", tags=["Items"])
# ↓↓↓ 追加
api_router.include_router(users.router, prefix="/users", tags=["Users"])
