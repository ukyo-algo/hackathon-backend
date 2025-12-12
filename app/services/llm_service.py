# hackathon-backend/app/services/llm_service.py

import os
import json
from google import genai
from google.genai import types
from google.genai.errors import APIError
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from fastapi import HTTPException
from google.oauth2 import service_account  # サービスアカウント認証用

from app.core.config import settings
from app.db import models
from app.api.v1.endpoints.items import get_items  # 削除せず維持

# --- LLM クライアントの定義 ---
# グローバル変数としてクライアントを保持
client = None


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
            creds_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        # 5. JSONの中からプロジェクトIDも自動取得
        project_id = creds_info.get("project_id")

        # 6. クライアント初期化
        client = genai.Client(
            vertexai=True, project=project_id, location="us-central1", credentials=creds
        )

        print(
            f"✅ Gemini Client Initialized with Service Account (Project: {project_id})"
        )
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
        # クライアント初期化処理を関数に委譲
        self.client = get_gemini_client()

        # 循環参照を避けるため、ItemServiceのインポートとインスタンス化を遅延させる
        self.item_service = self.get_item_service()

    def get_item_service(self):
        # 現状ではItemServiceを定義していないため、ここではダミー関数やサービスを返す
        class DummyItemService:
            def get_popular_item(self_dummy):
                # importしたmodelsを使用
                return (
                    self.db.query(models.Item)
                    .order_by(models.Item.created_at.desc())
                    .first()
                )

            def get_random_item(self_dummy):
                # ランダム取得のロジック（簡易実装）
                return self.db.query(models.Item).first()

        # データベースセッションを利用するために、DummyItemServiceのインスタンスを返す
        return DummyItemService()

    # ----------------------------------------------
    # 1. LLM対話機能のコア (キャラクターなりきり)
    # ----------------------------------------------
    def chat_with_persona(self, user_id: str, message: str) -> dict:
        """
        ユーザーの設定中のペルソナになりきって返信する
        """
        # クライアントが利用可能かチェック
        if not self.client:
            return {
                "reply": "申し訳ありません。AIシステムが停止しています。管理者に報告してください。",
                "persona": {"name": "エラー", "avatar_url": "", "theme": "error"},
            }

        # 1. ユーザーと現在セット中のキャラを取得
        user = (
            self.db.query(models.User)
            .filter(models.User.firebase_uid == user_id)
            .first()
        )

        current_persona = None

        # 2. キャラ設定の取得とフォールバック処理
        if user and user.current_persona:
            current_persona = user.current_persona
        elif user:
            # current_persona_id が未設定だが、所持ペルソナがある場合は先頭を自動セット
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
                # 所持なしの場合はデフォルト(1)をセット
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
            # ユーザーが見つからない場合のフォールバック
            default_persona = (
                self.db.query(models.AgentPersona)
                .filter(models.AgentPersona.id == 1)
                .first()
            )
            if default_persona:
                current_persona = default_persona

        # 3. プロンプトと情報の構築
        if current_persona:
            system_instruction = current_persona.system_prompt
            persona_info = {
                "name": current_persona.name,
                "avatar_url": current_persona.avatar_url,
                "theme": current_persona.theme_color,
            }
        else:
            # 最終防衛ライン
            system_instruction = (
                "あなたは親切なAIアシスタントです。優しくサポートしてください。"
            )
            persona_info = {
                "name": "AIアシスタント",
                "avatar_url": "/avatars/default.png",
                "theme": "default",
            }

        # 4. Geminiへの設定
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )

        try:
            # 5. Geminiにメッセージを送信
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[message],
                config=config,
            )

            return {"reply": response.text, "persona": persona_info}

        except APIError as e:
            print(f"LLM API Error: {e}")
            return {
                "reply": f"通信エラーが発生しました。サーバー認証を確認してください。詳細: {e}",
                "persona": persona_info,
            }
        except Exception as e:
            print(f"LLM Unhandled Error: {e}")
            return {
                "reply": "あ、ごめんなさい... 予期せぬエラーで応答できません。",
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
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

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
                model=self.model_name, contents=[image_part, prompt_text], config=config
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
