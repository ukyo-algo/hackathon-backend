from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# .db.database から app.db.database に修正（または環境に合わせて）
from app.db.database import get_db, engine, Base
from fastapi.middleware.cors import CORSMiddleware

# ↓↓↓ 1. v1のAPIルーターをインポートします
from app.api.v1.api import api_router

app = FastAPI()

# Vercelとの接続
origins = [
    "https://hackathon-frontend-theta.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ↓↓↓ 2. /api/v1 プレフィックスで v1ルーターを接続します
# (これが /api/v1/items などを有効にします)
app.include_router(api_router, prefix="/api/v1")


# --- 以下、既存のコード ---


@app.get("/api/v1/ping")
def ping():
    """
    疎通確認用のエンドポイント.
    """
    return {"status": "success"}


@app.get("/users/")
def read_users(db: Session = Depends(get_db)):
    # users = db.query(models.User).all()
    # return users
    return {"message": "DB connection successful (setup example)"}


@app.get("/")
def read_root():
    return {"message": "Hello World from FastAPI!"}
