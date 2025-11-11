from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# ↓↓↓ 必要なモジュールを追加
from typing import List
from app.db import models  # db/models.py をインポート
from app.schemas import user as user_schema  # schemas/user.py をインポート

# ↑↑↑
from app.db.database import get_db, engine, Base
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router

app = FastAPI(title="FleaMarketApp API", version="1.0.0")

# Vercelとの接続
origins = [
    "https://hackathon-frontend-theta.vercel.app",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/v1 プレフィックスで v1ルーターを接続
app.include_router(api_router, prefix="/api/v1")


# --- 以下、既存のコード ---


@app.get("/api/v1/ping")
def ping():
    """
    疎通確認用のエンドポイント.
    """
    return {"status": "success"}


# ↓↓↓ ここのエンドポイントを修正
@app.get(
    "/users/",
    response_model=List[user_schema.UserBase],  # 1. レスポンスの「形」を指定
    tags=["Test (Users)"],  # 2. (推奨) /docs での分類タグ
)
def read_users(db: Session = Depends(get_db)):
    """
    データベースから全ユーザーを取得する（テスト用）
    """
    # 3. コメントアウトを解除
    users = db.query(models.User).all()
    # 4. users を返す
    return users
    # return {"message": "DB connection successful (setup example)"} # 古い行は削除


@app.get("/")
def read_root():
    return {"message": "Hello World from FastAPI!"}
