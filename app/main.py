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
from app.db.database import get_db, engine, Base, SessionLocal
from app.api.v1.api import api_router

# ★修正: seed_if_empty のインポートを削除。起動時には呼ばない。

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

        # 3. 初期データの自動投入 (削除/コメントアウト)
        # 起動時間の問題があるため、この処理は手動で実行する

    except Exception as e:
        print(f"⚠️ Startup error: {e}")
        # 例外発生時も起動プロセスを停止させず、アプリを起動させる
        # DB接続失敗時もヘルスチェックをパスするため


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

# --- スタティックファイル (デモ画像) ---
# フロントエンドの public/demo_products をマウント
demo_products_path = os.path.join(
    os.path.dirname(__file__), "../..", "hackathon-frontend/public/demo_products"
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
