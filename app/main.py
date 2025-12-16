# hackathon-backend/app/main.py

import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List

# 必要なモジュール
from app.db import models
from app.schemas import user as user_schema
from app.db.database import get_db, engine, Base
from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(title="FleaMarketApp API", version="1.0.0")


@app.on_event("startup")
def startup_event():
    # 1. DBエンジンの確認
    if engine is None:
        print("⚠️ Database engine is None. Skipping operations.")
        # DB接続が失敗しても、FastAPI自体は起動させておく（ヘルスチェックをパスするため）
        return

    try:
        # 2. テーブル作成 (存在しない場合のみ作成されるため高速)
        Base.metadata.create_all(bind=engine)
        print("✅ Tables check passed.")

    except Exception as e:
        print(f"⚠️ Startup error: {e}")
        # 例外発生時も起動プロセスを停止させず、アプリを起動させる
        # DB接続失敗時もヘルスチェックをパスするため


# --- CORS設定 ---
# CORS設定: 本番・開発・Vercelプレビューを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ルーター ---
app.include_router(api_router, prefix="/api/v1")

# --- スタティックファイル (デモ画像) ---
# フロントエンドの public/demo_products をマウント
demo_products_path = os.path.join(
    os.path.dirname(__file__), settings.STATIC_FILES_PATH
)
if os.path.exists(demo_products_path):
    app.mount(
        "/demo_products",
        StaticFiles(directory=demo_products_path),
        name="demo_products",
    )
    print(f"✅ Demo products mounted: {demo_products_path}")
else:
    print(f"⚠️ Demo products directory not found: {demo_products_path}")


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
