# hackathon-backend/seed.py

import os
import random
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text

load_dotenv()

try:
    from app.db.database import SessionLocal, engine, Base
    from app.db.models import (
        User,
        Item,
        Transaction,
        Like,
        Comment,
        AgentPersona,
        UserPersona,
    )
except ImportError:
    # パス解決がうまくいかない場合のフォールバック（直接実行時など）
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from app.db.database import SessionLocal, engine, Base
    from app.db.models import (
        User,
        Item,
        Transaction,
        Like,
        Comment,
        AgentPersona,
        UserPersona,
    )

# --- 定数定義 ---
NUM_ITEMS_TO_GENERATE = 20

CATEGORIES = ["ファッション", "家電・スマホ・カメラ", "靴", "PC周辺機器", "その他"]
CONDITIONS = [
    "新品、未使用",
    "未使用に近い",
    "目立った傷や汚れなし",
    "やや傷や汚れあり",
    "傷や汚れあり",
    "全体的に状態が悪い",
]
BRANDS = [
    "Nike",
    "Adidas",
    "Apple",
    "Sony",
    "Uniqlo",
    "Zara",
    "Gucci",
    "Supreme",
    "Anker",
    "Logicool",
    "不明",
]

# --- LLM キャラクター定義 ---
PERSONAS_DATA = [
    {
        "id": 1,
        "name": "ドット絵の青年",
        "rarity": 1,
        "system_prompt": """
あなたはフリマアプリの親切で実直な案内人です。
一人称は「僕」です。
ユーザーのことを「お客さん」と呼びます。
言葉遣いは少し砕けた敬語を使ってください（例：「〜ですね」「〜だと思いますよ」）。
フリマの初心者にも優しくアドバイスをします。
絵文字は控えめに、ドット絵のようなレトロな温かみのある雰囲気を醸し出してください。
""",
        "avatar_url": "/avatars/male1.png",
        "background_theme": "pixel_retro",
    },
    # 将来的に追加するキャラ（執事など）はここに追記
]


def seed_data():
    print("Seeding database...")
    db: Session = SessionLocal()

    try:
        # テーブル再作成（既存データはリセットされます）
        print("Dropping & Creating tables...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # ---------------------------
        # 1. キャラクター（AgentPersona）の投入
        # ---------------------------
        print("Creating Agent Personas...")
        for p_data in PERSONAS_DATA:
            persona = AgentPersona(
                id=p_data["id"],
                name=p_data["name"],
                description="デフォルトキャラクター",
                system_prompt=p_data["system_prompt"],
                avatar_url=p_data["avatar_url"],
                background_theme=p_data["background_theme"],
                rarity=p_data["rarity"],
            )
            db.add(persona)
        db.commit()

        # ---------------------------
        # 2. ダミーユーザーの投入
        # ---------------------------
        print("Creating Users...")
        # 全員、初期状態でID:1（ドット絵の青年）をセット
        users_data = [
            {
                "firebase_uid": "uid_1",
                "username": "Seller A",
                "email": "a@test.com",
                "points": 100,
                "current_persona_id": 1,
            },
            {
                "firebase_uid": "uid_2",
                "username": "Buyer B",
                "email": "b@test.com",
                "points": 100,
                "current_persona_id": 1,
            },
            {
                "firebase_uid": "uid_3",
                "username": "User C",
                "email": "c@test.com",
                "points": 100,
                "current_persona_id": 1,
            },
        ]

        created_users = []
        for u_data in users_data:
            user = User(**u_data)
            db.add(user)
            created_users.append(user)
        db.commit()

        user_ids = [u.firebase_uid for u in created_users]

        # ---------------------------
        # 3. 所持キャラ情報（UserPersona）の投入
        # ---------------------------
        print("Granting Personas...")
        for uid in user_ids:
            # ID:1 のキャラを所持リストに追加
            up = UserPersona(user_id=uid, persona_id=1, favorability=0)
            db.add(up)
        db.commit()

        # ---------------------------
        # 4. アイテム・取引・エンゲージメントの投入
        # ---------------------------
        print("Creating Items, Likes, Comments...")
        for i in range(NUM_ITEMS_TO_GENERATE):
            seller_id = random.choice(user_ids)
            category = random.choice(CATEGORIES)

            item = Item(
                name=f"ダミーアイテム {i+1}",
                description=f"これは {category} のダミー商品です。状態は良好です。",
                price=random.randint(500, 15000),
                category=category,
                brand=random.choice(BRANDS),
                condition=random.choice(CONDITIONS),
                image_url=f"https://picsum.photos/id/{random.randint(1, 100)}/400/300",
                is_instant_buy_ok=random.choice([True, False]),
                status="on_sale",
                seller_id=seller_id,
            )

            # ランダムにいいね
            for uid in user_ids:
                if uid != seller_id and random.random() < 0.3:
                    db.add(Like(user_id=uid, item=item))

            # ランダムにコメント
            for uid in user_ids:
                if uid != seller_id and random.random() < 0.2:
                    db.add(
                        Comment(
                            user_id=uid,
                            item=item,
                            content="気になります！値下げ可能ですか？",
                        )
                    )

            db.add(item)

        db.commit()
        print("Seeding complete! ✅")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
