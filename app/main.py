from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .database import get_db, engine, Base
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Vercelとの接続
origins = ["https://hackathon-frontend-theta.vercel.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
