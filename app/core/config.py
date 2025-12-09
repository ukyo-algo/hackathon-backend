import os
from dotenv import load_dotenv

# .envファイルを読み込む（ローカル開発用）
load_dotenv()


class Settings:
    # API設定
    API_V1_STR: str = "/api/v1"

    # DB設定 (database.pyと合わせる)
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv(
        "DB_PASS", "password"
    )  # .envではDB_PASSとなっているため合わせます
    DB_HOST: str = os.getenv("INSTANCE_CONNECTION_NAME", "localhost")
    DB_NAME: str = os.getenv("DB_NAME", "hackathon")

    # LLM (Gemini) 設定
    # Cloud Run環境変数、または.envから読み込みます
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-1.5-flash"


settings = Settings()
