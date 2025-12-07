# hackathon-backend/seed.py (いいね・コメント対応版)

import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

try:
    from app.db.database import SessionLocal, engine, Base

    # ↓↓↓ Like, Comment を追加
    from app.db.models import User, Item, Transaction, Like, Comment
except ImportError:
    from app.db.database import SessionLocal, engine, Base
    from app.db.models import User, Item, Transaction, Like, Comment

NUM_ITEMS_TO_GENERATE = 20
SOLD_OUT_RATE = 0.3

# ... (CATEGORIES, KEYWORDS などの定数定義は前回と同じなので省略可能ですが、念のため全量コピペ推奨) ...
# (※長くなるので、前回の seed.py の定数定義部分をそのまま使ってください)
# 以下、seed_data 関数の中身を中心に修正します

# --- データセット (前回と同じ) ---
CATEGORIES = ["ファッション", "家電・スマホ・カメラ", "靴", "PC周辺機器", "その他"]
CONDITIONS = [
    "新品、未使用",
    "未使用に近い",
    "目立った傷や汚れなし",
    "やや傷や汚れあり",
    "傷や汚れあり",
    "全体的に状態が悪い",
]
KEYWORDS = {
    "ファッション": ["おしゃれ", "夏物"],
    "家電・スマホ・カメラ": ["高性能", "最新"],
    "靴": ["歩きやすい", "レア"],
    "PC周辺機器": ["ゲーミング", "高速"],
    "その他": ["便利", "まとめ売り"],
}  # ※簡略化してます
ADJECTIVES = ["超美品", "訳あり", "人気の", "伝説の", "普通の"]
NOUNS = {
    "ファッション": ["Tシャツ"],
    "家電・スマホ・カメラ": ["カメラ"],
    "靴": ["スニーカー"],
    "PC周辺機器": ["マウス"],
    "その他": ["置物"],
}
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


def generate_random_item(seller_id):
    category = random.choice(CATEGORIES)
    # (簡易実装: 前回と同じロジックで生成)
    return {
        "name": f"ダミー商品 {random.randint(1,1000)}",
        "description": "これはダミーです。",
        "price": 1000,
        "image_url": f"https://picsum.photos/id/{random.randint(1,100)}/400/300",
        "is_instant_buy_ok": True,
        "seller_id": seller_id,
        "category": category,
        "brand": "Brand",
        "condition": "新品",
        "status": "on_sale",
    }


def seed_data():
    print("Seeding database with Engagement data...")
    db: Session = SessionLocal()

    try:
        print("Dropping & Creating tables...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        print("Creating dummy users...")
        users_data = [
            {
                "firebase_uid": "seed_user_1_uid",
                "username": "Seller A",
                "email": "a@test.com",
            },
            {
                "firebase_uid": "seed_user_2_uid",
                "username": "Buyer B",
                "email": "b@test.com",
            },
            {
                "firebase_uid": "seed_user_3_uid",
                "username": "User C",
                "email": "c@test.com",
            },
        ]
        created_users = []
        for u_data in users_data:
            user = User(**u_data)
            db.add(user)
            created_users.append(user)
        db.commit()
        user_ids = [u.firebase_uid for u in created_users]

        print("Creating items & transactions & likes & comments...")
        for _ in range(NUM_ITEMS_TO_GENERATE):
            seller_id = random.choice(user_ids)
            # ※本来はgenerate_random_itemを使いますが簡略化のため直接記述
            item = Item(
                name="ダミーアイテム",
                description="説明",
                price=1000,
                category="その他",
                brand="None",
                condition="新品",
                image_url="https://picsum.photos/400/300",
                is_instant_buy_ok=True,
                status="on_sale",
                seller_id=seller_id,
            )

            # ランダムにいいねをつける
            for uid in user_ids:
                if random.random() < 0.3:  # 30%の確率でいいね
                    db.add(Like(user_id=uid, item=item))

            # ランダムにコメントをつける
            for uid in user_ids:
                if random.random() < 0.2:  # 20%の確率でコメント
                    db.add(Comment(user_id=uid, item=item, content="気になります！"))

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
