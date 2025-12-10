# app/main.py

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

# 必要なモジュール
from app.db import models
from app.schemas import user as user_schema
from app.db.database import get_db, engine, Base, SessionLocal
from app.api.v1.api import api_router

# シードロジックのインポート
from app.db.seed import seed_if_empty

app = FastAPI(title="FleaMarketApp API", version="1.0.0")


@app.on_event("startup")
def startup_event():
    # 1. DBエンジンの確認
    if engine is None:
        print("⚠️ Database engine is None. Skipping operations.")
        return

    try:
        # 2. テーブル作成 (存在しない場合のみ作成される)
        Base.metadata.create_all(bind=engine)
        print("✅ Tables check passed.")

        # 3. 初期データの自動投入 (空の場合のみ)
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()

    except Exception as e:
        print(f"⚠️ Startup error: {e}")


# --- CORS設定 ---
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

# --- ルーター ---
app.include_router(api_router, prefix="/api/v1")


# --- 簡易エンドポイント ---
@app.get("/api/v1/ping")
def ping():
    return {"status": "success"}


@app.get("/users/", response_model=List[user_schema.UserBase], tags=["Test"])
def read_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()


@app.get("/")
def read_root():
    return {"message": "Hello World from FastAPI!"}
