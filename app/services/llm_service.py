# hackathon-backend/app/services/llm_service.py

import os
from google import genai
from google.genai import types
from sqlalchemy.orm import Session
from app.db import models

# APIキー設定（環境変数から読み込み）
# Vertex AIの場合は project 引数などが必要ですが、今回はAPI Key方式を想定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)


class LLMService:
    def __init__(self, db: Session):
        self.db = db
        self.model_name = "gemini-1.5-flash"  # 無料枠で高速なモデル

    def chat_with_persona(self, user_id: str, message: str) -> dict:
        """
        ユーザーの設定中のペルソナになりきって返信する
        """
        # 1. ユーザー取得
        user = (
            self.db.query(models.User)
            .filter(models.User.firebase_uid == user_id)
            .first()
        )

        current_persona = None

        # 2. キャラ設定の取得とフォールバック処理
        if user and user.current_persona:
            current_persona = user.current_persona
        else:
            # ★変更点: 設定がない場合は ID:1 (ドット絵の青年) をデフォルトとして取得
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
                "theme": current_persona.background_theme,
            }
        else:
            # 万が一DBにID:1すらない場合の最終防衛ライン（コードでハードコーディング）
            system_instruction = """
            あなたはフリマアプリの親切な案内人（ドット絵の青年）です。
            一人称は「僕」です。ユーザーを「お客さん」と呼び、優しくサポートしてください。
            """
            persona_info = {
                "name": "ドット絵の青年",
                "avatar_url": "/avatars/male1.png",
                "theme": "pixel_retro",
            }

        # 4. Geminiへの設定
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )

        try:
            # 5. Geminiにメッセージを送信
            response = client.models.generate_content(
                model=self.model_name,
                contents=[message],
                config=config,
            )

            return {"reply": response.text, "persona": persona_info}

        except Exception as e:
            print(f"LLM Error: {e}")
            return {
                "reply": "あ、ごめんなさい... 通信がうまくいかないみたいです。（エラー）",
                "persona": persona_info,
            }
