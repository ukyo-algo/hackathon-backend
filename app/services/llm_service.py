# hackathon-backend/app/services/llm_service.py

import json
from pathlib import Path
from google import genai
from google.genai import types
from google.genai.errors import APIError
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from fastapi import HTTPException
from google.oauth2 import service_account  # サービスアカウント認証用

from app.core.config import settings
from app.db import models

# from app.api.v1.endpoints.items import get_items  # 未使用のためコメントアウト

# --- LLM クライアントの定義 ---
# グローバル変数としてクライアントを保持
client = None
WEB_INFO = None


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
    global client
    if client is not None:
        return client

    # 1. config.py経由で環境変数の文字列を取得
    sa_key_string = settings.GEMINI_SA_KEY

    # 2. 認証情報の確認
    if not sa_key_string:
        print("⚠️ GEMINI_SA_KEY is empty. AI features will be disabled.")
        return None

    try:
        # 3. JSON文字列を辞書(dict)に変換
        creds_info = json.loads(sa_key_string)

        # 4. 認証オブジェクトを作成 (★修正: scopesを追加)
        # ここで「Google Cloudを使います」と宣言しないと invalid_scope エラーになります
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=[
                "https://www.googleapis.com/auth/cloud-platform",
            ],
        )

        # 5. JSONの中からプロジェクトIDも自動取得
        project_id = creds_info.get("project_id")

        # 6. クライアント初期化
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location="us-central1",
            credentials=creds,
        )

        print(f"✅ Gemini Client initialized (Project: {project_id})")
        return client

    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: 環境変数のJSONが壊れています。\nError: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Gemini Client Initialization Failed: {e}")
        return None


class LLMService:
    def __init__(self, db: Session):
        self.db = db
        self.model_name = settings.GEMINI_MODEL
        self.client = get_gemini_client()
        global WEB_INFO
        if WEB_INFO is None:
            WEB_INFO = _load_web_info()
        self.item_service = self.get_item_service()
        # --- ここを追加: 履歴一元管理 ---
        self.history: List[dict] = []

    def append_history(self, entry: dict):
        """履歴にエントリを追加"""
        self.history.append(entry)
        # 必要なら履歴長制限もここで実装

    def reset_history(self):
        """履歴をリセット"""
        self.history = []

    def chat_with_persona(
        self,
        user_id: str,
        current_chat: str,
        history: List[dict] = None,  # 外部履歴は受け取るが使用しない（LLMServiceで一元管理）
    ) -> dict:
        # ユーザーと現在セット中のキャラを取得し、system_instructionとpersona_infoを準備
        current_persona = None
        persona_info = {
            "name": "AIアシスタント",
            "avatar_url": "/avatars/default.png",
            "theme": "default",
        }
        system_instruction = (
            "あなたは親切なAIアシスタントです。優しくサポートしてください。"
        )

        try:
            user = (
                (
                    self.db.query(models.User)
                    .filter(models.User.firebase_uid == user_id)
                    .first()
                )
                if user_id
                else None
            )
        except Exception:
            user = None

        if user and user.current_persona:
            current_persona = user.current_persona
        elif user:
            # 所持ペルソナの先頭を自動セット、なければデフォルト(1)
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
                current_persona = first_owned
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
                    current_persona = default_persona
        else:
            # ユーザー不在時もデフォルトを試みる
            default_persona = (
                self.db.query(models.AgentPersona)
                .filter(models.AgentPersona.id == 1)
                .first()
            )
            if default_persona:
                current_persona = default_persona

        if current_persona:
            system_instruction = current_persona.system_prompt or system_instruction
            persona_info = {
                "name": current_persona.name,
                "avatar_url": current_persona.avatar_url,
                "theme": current_persona.theme_color,
            }

        if WEB_INFO and isinstance(WEB_INFO, dict):
            try:
                routes = WEB_INFO.get("routes", [])
                notes = WEB_INFO.get("guidance", {}).get("notes", [])
                lines = [
                    "[WEB_INFO] アプリの主要ページと用途の要点:",
                ]
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
                web_info_text = "\n".join(lines)
                # --- 指示文を削除し、情報のみ付与 ---
                system_instruction = f"{system_instruction}\n\n{web_info_text}\n\n"
            except Exception as e:
                print(f"⚠️ WEB_INFO build failed: {e}")

        # --- 履歴一元管理: self.historyのみを使用 ---
        # 外部からのhistoryは無視し、サービス内のself.historyだけで文脈を構築する
        # guidance(system/type)も含めてsystem_instructionに反映
        last_guidance = None
        for h in reversed(self.history):
            if (
                h.get("role") == "system"
                and h.get("type") == "guidance"
                and h.get("content")
            ):
                last_guidance = h.get("content")
                break
        if last_guidance:
            system_instruction = (
                f"{system_instruction}\n\n[PAGE CONTEXT]\n{last_guidance}"
            )

        # Geminiへの設定
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )

        try:
            contents = []
            # self.historyをもとに会話履歴を構築
            for h in self.history:
                role = h.get("role", "user")
                content = h.get("content", "")
                if h.get("type") == "guidance" or not content:
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part(text=content)],
                        )
                    )
                elif role == "ai":
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part(text=content)],
                        )
                    )
                else:
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part(text=content)],
                        )
                    )
            # 今回のメッセージは履歴にはまだ追加せず、生成にのみ使用
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=current_chat)],
                )
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )
            # 生成後に今回の発話とAI応答を履歴へ追加
            self.append_history({"role": "user", "content": current_chat})
            self.append_history({"role": "ai", "content": response.text})
            return {"reply": response.text, "persona": persona_info}

        except APIError as e:
            print(f"LLM API Error: {e}")
            return {
                "reply": (
                    "通信が不安定なようです。どのカテゴリや価格帯を検討中か教えていただければ、"
                    "今できる範囲で候補や比較観点を提案します。"
                ),
                "persona": persona_info,
            }
        except Exception as e:
            print(f"LLM Unhandled Error: {e}")
            return {
                "reply": (
                    "少し不具合が発生しました。差し支えなければ、目的や条件（例: 1万円以内のワイヤレスイヤホン）"
                    "を教えてください。できる範囲で候補や相場のヒントを返します。"
                ),
                "persona": persona_info,
            }

    # ----------------------------------------------
    # 2. 出品説明文の自動生成 (Vision機能)
    # ----------------------------------------------
    async def generate_item_description(
        self, image_bytes: bytes, item_name: str
    ) -> Dict[str, Any]:
        """
        画像と商品名から説明文、カテゴリ、ブランドを生成する
        """
        if not self.client:
            raise HTTPException(status_code=503, detail="AIサービスが利用できません。")

        # 画像データを Part オブジェクトに変換 (mime_typeは適宜調整)
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg",
        )

        # LLMに出力させたいJSONスキーマを定義
        json_schema = {
            "type": "object",
            "properties": {
                "description_text": {
                    "type": "string",
                    "description": "商品の魅力を最大限に引き出す、丁寧な長文の説明文。",
                },
                "category_guess": {
                    "type": "string",
                    "description": "画像から判断した最も適切なカテゴリ。",
                },
                "brand_guess": {
                    "type": "string",
                    "description": "画像または商品名から判断したブランド名。不明な場合は'不明'と回答。",
                },
                "condition_suggest": {
                    "type": "string",
                    "description": "商品の状態を提案。",
                },
            },
            "required": [
                "description_text",
                "category_guess",
                "brand_guess",
                "condition_suggest",
            ],
        }

        # プロンプト（AIへの依頼）
        prompt_text = (
            f"あなたはプロのフリマ出品代行AIです。提供された画像と商品名『{item_name}』を元に、"
            f"最高の出品説明文と、適切な分類情報をJSON形式で出力してください。出力は必ずJSONスキーマに従ってください。"
        )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=json_schema,
            temperature=0.4,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[image_part, prompt_text],
                config=config,
            )
            # JSON形式で返ってくるため、パースして返す
            return json.loads(response.text)
        except APIError as e:
            raise HTTPException(status_code=500, detail=f"LLM APIエラー: {e}")
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500, detail="LLMからのレスポンスが不正なJSON形式です。"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"予期せぬエラー: {e}")

    # ----------------------------------------------
    # 3. ログイン時のおすすめ商品生成 (アイテムサービスとの連携)
    # ----------------------------------------------
    def generate_login_recommendation(self, firebase_uid: str) -> Dict[str, Any]:
        """
        ログイン時に、設定されたキャラの性格に基づいたおすすめ商品とコメントを生成
        """
        # このメソッドはデモ用であり、現在はダミーのロジックです
        if not self.client:
            return {"comment": "AIシステムが利用できません。", "item": None}

        user = (
            self.db.query(models.User)
            .filter(models.User.firebase_uid == firebase_uid)
            .first()
        )

        # ユーザーとキャラが紐付いていない場合のフォールバック
        if not user or not user.current_persona:
            item = self.item_service.get_popular_item()
            return {
                "comment": "ようこそ！早速、人気のアイテムを見てみましょう！",
                "item": item,
            }

        persona = user.current_persona

        # 簡易的なロジック切り替え
        if "執事" in persona.name:
            item = (
                self.item_service.get_popular_item()
            )  # ダミー: ここで高度なマッチングを呼ぶ
            comment = "本日は、ご主人様にふさわしい逸品をご紹介いたします。"
        elif "ギャル" in persona.name:
            item = self.item_service.get_random_item()
            comment = "マジでヤバいアイテム見つけたんだけど、見てみて！👀"
        else:  # ドット絵の青年
            item = self.item_service.get_popular_item()
            comment = "おかえりなさい！今日は特に注目されている商品をご紹介しますね。"

        return {
            "comment": comment,
            "item": item,
            "persona_name": persona.name,
            "persona_avatar": persona.avatar_url,
        }


# グローバルなllm_serviceインスタンス（依存性注入で使用）
llm_service = None


def get_llm_service(db: Session) -> LLMService:
    """LLMServiceのインスタンスを取得"""
    return LLMService(db)
