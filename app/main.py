from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .database import get_db, engine, Base

app = FastAPI()


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
