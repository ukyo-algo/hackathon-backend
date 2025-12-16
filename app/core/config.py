# hackathon-backend/app/core/config.py

import os
from dotenv import load_dotenv

# .envファイルを読み込む（ローカル開発用）
# 本番環境（Cloud Runなど）ではファイルがないため無視されます
load_dotenv()


class Settings:
    # API設定
    API_V1_STR: str = "/api/v1"

    # DB設定 (database.pyと合わせる)
    DB_USER: str = os.getenv("DB_USER", "postgres")

    # .envではDB_PASSとなっているため、ここで名前を合わせて読み込みます
    DB_PASSWORD: str = os.getenv("DB_PASS", "password")

    # Cloud SQL接続名、またはローカルホスト
    DB_HOST: str = os.getenv("INSTANCE_CONNECTION_NAME", "localhost")
    DB_NAME: str = os.getenv("DB_NAME", "hackathon")

    # LLM (Gemini) 設定
    # Cloud Run環境変数、または.envから読み込みます
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ★追加: サービスアカウントのJSONキー文字列を受け取る設定
    # llm_service.py でこの値をパースして認証に使用します
    GEMINI_SA_KEY: str = os.getenv("GEMINI_SA_KEY", "")

    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Frontend/feature config knobs
    # おすすめ関連の件数とクールダウン（分）を環境変数から設定可能に
    RECOMMEND_ITEM_COUNT: int = int(os.getenv("RECOMMEND_ITEM_COUNT", "5"))
    RECOMMEND_COOLDOWN_MINUTES: int = int(os.getenv("RECOMMEND_COOLDOWN_MINUTES", "60"))

    # コイン報酬関連
    REWARD_AMOUNT: int = int(os.getenv("REWARD_AMOUNT", "1000"))
    REWARD_COOLDOWN_MINUTES: int = int(os.getenv("REWARD_COOLDOWN_MINUTES", "60"))

    # CORS設定
    CORS_ORIGINS: list = [
        "https://hackathon-frontend-theta.vercel.app",
        "http://localhost:3000",
    ]

    # パス設定
    STATIC_FILES_PATH: str = "../hackathon-frontend/public/demo_products"

    # DEBUG mode
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


# 設定インスタンスを作成してエクスポート
settings = Settings()
