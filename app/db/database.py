import sqlalchemy
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings  # ★修正: configから設定を読み込む

# Cloud SQL Connectorの初期化
connector = Connector()


def getconnection():
    """
    Cloud SQL への接続を確立する関数.
    config.py (settings) の値を使用します。
    """
    # settings.DB_HOST には INSTANCE_CONNECTION_NAME が入っています
    conn = connector.connect(
        settings.DB_HOST,
        "pymysql",
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,  # config.pyでは DB_PASS を DB_PASSWORD として読み込んでいます
        db=settings.DB_NAME,
        charset="utf8mb4",
    )
    return conn


# エンジンの作成
# ローカル実行時など、接続情報がない場合にクラッシュしないよう保護
try:
    engine = sqlalchemy.create_engine(
        "mysql+pymysql://",
        creator=getconnection,
    )
except Exception as e:
    print(f"Warning: Could not create database engine. {e}")
    engine = None

# セッション作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    DBセッションを取得するための依存関係.
    """
    if engine is None:
        raise Exception("Database engine is not initialized.")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
