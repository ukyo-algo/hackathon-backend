import os
import sqlalchemy
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy.orm import sessionmaker, declarative_base

connector = Connector()  # SQLとFastAPIをつなぐコネクタ

DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_NAME = os.environ["DB_NAME"]
INSTANCE_CONNECTION_NAME = os.environ["INSTANCE_CONNECTION_NAME"]


def getconnection() -> sqlalchemy.engine.base.Connection:
    """
    Cloud SQL への接続を確立する関数.
    """
    conn = connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pymysql",
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
    )
    return conn


engine = sqlalchemy.create_engine(
    "mysql+pymysql://",
    creator=getconnection,
)

# DBを生成する関数
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()  # モデルの基底クラス


def get_db():
    """
    DBセッションを取得するための依存関係.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
