# hackathon-backend/app/services/llm_base.py
"""
LLM基底クラス
Geminiクライアント初期化、WEB_INFO読み込み、共通ユーティリティを提供
"""

import json
from pathlib import Path
from google import genai
from google.genai import types
from sqlalchemy.orm import Session
from google.oauth2 import service_account

from app.core.config import settings
from app.db import models


# --- グローバル変数 ---
_client = None
_web_info = None


def _load_web_info():
    """app/web_info/web_info.json を読み込む（存在しなければ None）"""
    try:
        base = Path(__file__).resolve().parent.parent  # app/
        p = base / "web_info" / "web_info.json"
        if not p.exists():
            return None
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ WEB_INFO load failed: {e}")
        return None


def get_gemini_client():
    """Geminiクライアントを取得または初期化する (レイジー初期化)"""
    global _client
    if _client is not None:
        return _client

    sa_key_string = settings.GEMINI_SA_KEY
    if not sa_key_string:
        print("⚠️ GEMINI_SA_KEY is empty. AI features will be disabled.")
        return None

    try:
        creds_info = json.loads(sa_key_string)
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        project_id = creds_info.get("project_id")
        _client = genai.Client(
            vertexai=True,
            project=project_id,
            location="us-central1",
            credentials=creds,
        )
        print(f"✅ Gemini Client initialized (Project: {project_id})")
        return _client
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Gemini Client Initialization Failed: {e}")
        return None


class LLMBase:
    """LLMサービスの基底クラス"""
    
    def __init__(self, db: Session):
        self.db = db
        self.model_name = settings.GEMINI_MODEL
        self.client = get_gemini_client()
        
        global _web_info
        if _web_info is None:
            _web_info = _load_web_info()
        self.web_info = _web_info

    def _load_history(self, user_id: str, limit: int = 50) -> list:
        """ユーザーのチャット/ガイダンス履歴を古い順で最大limit件取得"""
        if not user_id:
            return []
        try:
            rows = (
                self.db.query(models.ChatMessage)
                .filter(models.ChatMessage.user_id == user_id)
                .order_by(models.ChatMessage.created_at.asc())
                .limit(limit)
                .all()
            )
            return [
                {"role": r.role, "type": r.type, "content": r.content or ""}
                for r in rows
            ]
        except Exception as e:
            print(f"⚠️ load history failed: {e}")
            return []

    def _save_message(
        self, user_id: str, role: str, content: str, mtype: str | None = None
    ) -> None:
        """チャットメッセージをDBに保存"""
        if not user_id:
            return
        try:
            msg = models.ChatMessage(
                user_id=user_id, role=role, type=mtype, content=content
            )
            self.db.add(msg)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"⚠️ save message failed: {e}")

    def add_guidance(self, user_id: str, content: str) -> None:
        """ページ遷移等のガイダンスをsystem/guidanceとして保存"""
        self._save_message(
            user_id=user_id, role="system", content=content, mtype="guidance"
        )

    def log_interaction(self, user_id: str, interaction_type: str, data: dict) -> None:
        """すべてのLLM操作を履歴に保存（統一インターフェース）"""
        try:
            content = json.dumps(data, ensure_ascii=False)
            self._save_message(
                user_id=user_id, role="ai", content=content, mtype=interaction_type
            )
        except Exception as e:
            print(f"⚠️ log_interaction failed: {e}")

    def _get_user_persona(self, user_id: str):
        """ユーザーの現在のペルソナを取得"""
        try:
            user = (
                self.db.query(models.User)
                .filter(models.User.firebase_uid == user_id)
                .first()
                if user_id
                else None
            )
        except Exception:
            user = None

        if user and user.current_persona:
            return user, user.current_persona
        elif user:
            # 所持ペルソナの先頭を自動セット
            first_owned = (
                self.db.query(models.AgentPersona)
                .join(
                    models.UserPersona,
                    models.AgentPersona.id == models.UserPersona.persona_id,
                )
                .filter(models.UserPersona.user_id == user.id)
                .first()
            )
            if first_owned:
                user.current_persona_id = first_owned.id
                self.db.commit()
                self.db.refresh(user)
                return user, first_owned
            else:
                default_persona = (
                    self.db.query(models.AgentPersona)
                    .filter(models.AgentPersona.id == 1)
                    .first()
                )
                if default_persona:
                    user.current_persona_id = default_persona.id
                    self.db.commit()
                    self.db.refresh(user)
                    return user, default_persona
        else:
            # ユーザー不在時もデフォルトを返す
            default_persona = (
                self.db.query(models.AgentPersona)
                .filter(models.AgentPersona.id == 1)
                .first()
            )
            return None, default_persona
        
        return user, None

    def _build_web_info_text(self) -> str:
        """WEB_INFOからテキストを構築"""
        if not self.web_info or not isinstance(self.web_info, dict):
            return ""
        
        try:
            routes = self.web_info.get("routes", [])
            notes = self.web_info.get("guidance", {}).get("notes", [])
            lines = ["[WEB_INFO] アプリの主要ページと用途の要点:"]
            for r in routes:
                path = r.get("path")
                name = r.get("name")
                purpose = r.get("purpose")
                if path and name:
                    lines.append(f"- {name} ({path}): {purpose}")
            if notes:
                lines.append("[NOTES]")
                for n in notes:
                    lines.append(f"- {n}")
            return "\n".join(lines)
        except Exception:
            return ""
