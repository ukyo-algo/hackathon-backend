from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from typing import List

# 必要なモジュールをインポート
from app.db import models
from app.schemas import user as user_schema
from app.db.database import get_db, engine, Base
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db import models

app = FastAPI(title="FleaMarketApp API", version="1.0.0")


@app.on_event("startup")
def startup_event():
    # ★修正: engine が None（接続失敗）の場合はテーブル作成をスキップする安全装置
    if engine is None:
        print(
            "⚠️ Database engine is None. Skipping table creation. Check your DB connection settings."
        )
        return

    try:
        # FastAPIが起動し、ネットワーク接続が安定してからテーブル作成（DB接続）を実行
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created successfully.")
    except Exception as e:
        print(f"⚠️ Table creation failed: {e}")


# Vercelとの接続許可設定
origins = [
    "https://hackathon-frontend-theta.vercel.app",
    "http://localhost:3000",
    # 必要に応じて他のドメインを追加
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

# --- 以下、既存のエンドポイント ---


@app.get("/api/v1/ping")
def ping():
    """
    疎通確認用のエンドポイント.
    """
    return {"status": "success"}


@app.get(
    "/users/",
    response_model=List[user_schema.UserBase],
    tags=["Test (Users)"],
)
def read_users(db: Session = Depends(get_db)):
    """
    データベースから全ユーザーを取得する（テスト用）
    """
    users = db.query(models.User).all()
    return users


@app.get("/")
def read_root():
    return {"message": "Hello World from FastAPI!"}


@app.on_event("startup")
def startup_event():
    # ... (既存のテーブル作成処理)
    if engine is None:
        return
    Base.metadata.create_all(bind=engine)

    # ★追加: 初期キャラデータの投入
    db = SessionLocal()
    try:
        # キャラが1人もいなければ作成
        if db.query(models.AgentPersona).count() == 0:
            print("🚀 Seeding initial personas...")
            personas = [
                models.AgentPersona(
                    name="ドット絵の青年",
                    description="デフォルトのAIアシスタントです。",
                    system_prompt="あなたは親切なAIアシスタントです。フリマアプリのサポートを丁寧に行ってください。",
                    avatar_url="https://api.dicebear.com/7.x/pixel-art/svg?seed=user1",  # フリー素材
                    rarity=1,
                ),
                models.AgentPersona(
                    name="強気なギャル",
                    description="マジで頼りになるギャル店員。",
                    system_prompt="あなたはフリマアプリのカリスマ店員であるギャルです。「〜だし」「ウケる」などの口調で、フレンドリーかつ強気に接客してください。",
                    avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=Gal&eyebrows=unibrowNatural&clothing=collarAndSweater",
                    rarity=2,
                ),
                models.AgentPersona(
                    name="老練な執事",
                    description="あなたの出品を完璧にサポートします。",
                    system_prompt="あなたは英国紳士風の執事です。「〜でございます」「お任せください」などの口調で、極めて丁寧に出品をサポートしてください。",
                    avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=Butler&top=hat&facialHair=moustacheFancy",
                    rarity=3,
                ),
            ]
            db.add_all(personas)
            db.commit()
            print("✅ Personas seeded.")
    finally:
        db.close()
