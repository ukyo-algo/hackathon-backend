# backend/app/api/v1/api.py

from fastapi import APIRouter

# endpoints フォルダから items.py をインポート
from .endpoints import items

# v1用のメインルーター
api_router = APIRouter()

# items.router を /items というプレフィックスで登録
# これにより、/api/v1/items/... というURLが完成する
api_router.include_router(items.router, prefix="/items", tags=["Items"])

# (将来 users.py を作ったら、ここに追加する)
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
