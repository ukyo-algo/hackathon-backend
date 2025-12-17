# hackathon-backend/app/services/llm_service.py

import json
import random
from google.genai import types
from google.genai.errors import APIError
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from fastapi import HTTPException

from app.db import models
from app.services.llm_base import LLMBase
from app.services.prompts import (
    CHAT_OUTPUT_RULES,
    DEFAULT_SYSTEM_PROMPT,
    build_recommend_prompt,
)


class LLMService(LLMBase):
    """LLMサービス - LLMBaseを継承"""

    def chat_with_persona(
        self,
        user_id: str,
        current_chat: str,
        history: List[
            dict
        ] = None,  # 外部履歴は受け取るが使用しない（LLMServiceで一元管理）
    ) -> dict:
        # ユーザーと現在セット中のキャラを取得し、system_instructionとpersona_infoを準備
        current_persona = None
        persona_info = {
            "name": "AIアシスタント",
            "avatar_url": "/avatars/default.png",
            "theme": "default",
        }
        system_instruction = DEFAULT_SYSTEM_PROMPT

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
            # 返答は3〜4行、心中は省略
            system_instruction += CHAT_OUTPUT_RULES
            persona_info = {
                "name": current_persona.name,
                "avatar_url": current_persona.avatar_url,
                "theme": current_persona.theme_color,
            }

        # WEB_INFOをシステム指示に追加
        web_info_text = self._build_web_info_text()
        if web_info_text:
            system_instruction = f"{system_instruction}\n\n{web_info_text}\n\n"

        # --- 履歴: DBから読み込み（ユーザー別） ---
        history_rows = self._load_history(user_id=user_id, limit=200)
        # guidance(system/type)も含めてsystem_instructionに反映
        last_guidance = None
        for h in reversed(history_rows):
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
            # DB履歴をもとに会話履歴を構築
            for h in history_rows:
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
            # 生成後に今回の発話とAI応答をDB履歴へ追加
            self._save_message(
                user_id=user_id, role="user", content=current_chat, mtype="chat"
            )
            self._save_message(
                user_id=user_id, role="ai", content=response.text, mtype="chat"
            )
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
    # おすすめ生成API: 履歴/キーワードモード（クールダウン判定はフロントで実施）
    # ----------------------------------------------
    def generate_recommendations(
        self, user_id: str, mode: str, keyword: str | None = None
    ) -> Dict[str, Any]:
        """
        - mode: "history" | "keyword"
        - keyword: mode=="keyword"の時に使用
        - 4件（設定値）のアイテムとペルソナ質問文を返す
        """
        persona_info = {
            "name": "AIアシスタント",
            "avatar_url": "/avatars/default.png",
            "theme": "default",
        }

        # ペルソナ取得
        try:
            user = (
                self.db.query(models.User)
                .filter(models.User.firebase_uid == user_id)
                .first()
            )
        except Exception:
            user = None

        if user and user.current_persona:
            persona = user.current_persona
            persona_info = {
                "name": persona.name,
                "avatar_url": persona.avatar_url,
                "theme": persona.theme_color,
            }

        # アイテム候補を集める（4件）
        items = []
        try:
            item_count = getattr(settings, "RECOMMEND_ITEM_COUNT", 4)
            print(f"[generate_recommendations] Querying items with status='on_sale'")
            
            # まず全件数を確認
            total_items = self.db.query(models.Item).count()
            on_sale_items = self.db.query(models.Item).filter(models.Item.status == "on_sale").count()
            print(f"[generate_recommendations] Total items in DB: {total_items}, on_sale: {on_sale_items}")
            
            base_q = (
                self.db.query(models.Item)
                .filter(models.Item.status == "on_sale")
                .order_by(models.Item.created_at.desc())
            )
            # キーワードモードの場合、タイトル/説明のLIKEで粗く絞る
            if mode == "keyword" and keyword:
                like = f"%{keyword}%"
                base_q = base_q.filter(
                    (models.Item.name.ilike(like))
                    | (models.Item.description.ilike(like))
                )
            candidates = base_q.limit(50).all()
            print(f"[generate_recommendations] Candidates found: {len(candidates)}")
            
            random.shuffle(candidates)
            for it in candidates[:item_count]:
                items.append({
                    "item_id": str(getattr(it, "item_id", it.id)),
                    "name": getattr(it, "name", getattr(it, "title", "")),
                    "price": getattr(it, "price", None),
                    "image_url": getattr(it, "image_url", None),
                    "description": getattr(it, "description", None),
                })
            print(f"[generate_recommendations] Final items: {len(items)}")
        except Exception as e:
            print(f"[generate_recommendations] ERROR querying items: {e}")
            import traceback
            traceback.print_exc()
            items = []

        # ペルソナの口調で各商品の理由を生成
        item_reasons = {}
        try:
            system_instruction = "あなたは親切なAIアシスタントです。"
            if user and user.current_persona:
                system_instruction = user.current_persona.system_prompt or system_instruction

            # 商品リストをプロンプト用に整形
            items_text = "\n".join([
                f"- {it['name']} (¥{it['price']:,}): {(it.get('description') or '')[:100]}"
                for it in items
            ])
            
            prompt = build_recommend_prompt(keyword, mode, items_text)

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            )
            contents = [
                types.Content(role="user", parts=[types.Part(text=prompt)])
            ]
            resp = self.client.models.generate_content(
                model=self.model_name, contents=contents, config=config
            )
            
            # JSONをパース
            response_text = resp.text or "{}"
            print(f"DEBUG: LLM Response: {response_text}")

            # ```json ... ``` を除去
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            try:
                name_to_reason = json.loads(response_text.strip())
            except Exception as e:
                print(f"DEBUG: JSON decode failed: {e}")
                name_to_reason = {}
            
            # 商品名からitem_idにマッピング
            for it in items:
                item_name = it["name"]
                if item_name in name_to_reason:
                    item_reasons[it["item_id"]] = name_to_reason[item_name]
                else:
                    # 部分一致で探す
                    for name, reason in name_to_reason.items():
                        if name in item_name or item_name in name:
                            item_reasons[it["item_id"]] = reason
                            break
            print(f"DEBUG: Generated reasons: {item_reasons}")
        except Exception as e:
            print(f"⚠️ reason generation failed: {e}")

        # 履歴に保存（log_interactionを使用）
        self.log_interaction(user_id, "recommend", {
            "keyword": keyword,
            "mode": mode,
            "items": [{"item_id": it["item_id"], "name": it["name"]} for it in items],
            "reasons": item_reasons,
        })

        return {
            "can_recommend": True,
            "items": items,
            "reasons": item_reasons,  # {item_id: reason}
            "keyword": keyword,
            "mode": mode,
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


# グローバルなllm_serviceインスタンス（依存性注入で使用）
llm_service = None


def get_llm_service(db: Session) -> LLMService:
    """LLMServiceのインスタンスを取得"""
    return LLMService(db)
