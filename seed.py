# hackathon-backend/seed.py

import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# --- .envファイルを読み込む ---
load_dotenv()

# --- 環境変数が読み込まれた後に、DBモジュールをインポートする ---
try:
    from app.db.database import SessionLocal, engine, Base

    # ↓↓↓ Transaction を追加
    from app.db.models import User, Item, Transaction
except ImportError:
    from app.db.database import SessionLocal, engine, Base

    # ↓↓↓ Transaction を追加
    from app.db.models import User, Item, Transaction

# --- 設定 ---
NUM_ITEMS_TO_GENERATE = 400  # 自動生成するアイテム数
SOLD_OUT_RATE = 0.3  # 売り切れ商品の割合 (30%)

# --- データセット ---
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
    "ファッション": [
        "おしゃれ",
        "夏物",
        "冬物",
        "ビンテージ",
        "トレンド",
        "着心地",
        "限定",
        "セール",
        "韓国風",
        "ストリート",
    ],
    "家電・スマホ・カメラ": [
        "高性能",
        "最新",
        "美品",
        "動作確認済み",
        "ジャンク",
        "4K",
        "Bluetooth",
        "ワイヤレス",
        "軽量",
        "コンパクト",
    ],
    "靴": [
        "歩きやすい",
        "ランニング",
        "レザー",
        "スニーカー",
        "ブーツ",
        "防水",
        "カジュアル",
        "フォーマル",
        "レア",
        "コラボ",
    ],
    "PC周辺機器": [
        "ゲーミング",
        "高速",
        "USB-C",
        "RGB",
        "静音",
        "エルゴノミクス",
        "4K対応",
        "SSD",
        "メカニカル",
        "無線",
    ],
    "その他": [
        "便利",
        "まとめ売り",
        "引越し",
        "処分",
        "ハンドメイド",
        "ギフト",
        "日用品",
        "雑貨",
        "レアもの",
        "アンティーク",
    ],
}

ADJECTIVES = [
    "超美品",
    "訳あり",
    "人気の",
    "伝説の",
    "普通の",
    "少し古い",
    "最高級",
    "お買い得",
    "謎の",
    "愛用の",
]
NOUNS = {
    "ファッション": ["Tシャツ", "ジャケット", "コート", "パンツ", "帽子", "マフラー"],
    "家電・スマホ・カメラ": ["カメラ", "スマホ", "ヘッドホン", "スピーカー", "充電器"],
    "靴": ["スニーカー", "革靴", "サンダル", "ブーツ", "運動靴"],
    "PC周辺機器": ["マウス", "キーボード", "モニター", "ケーブル", "ハブ"],
    "その他": ["置物", "本", "チケット", "フィギュア", "食器"],
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
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS[category])

    name = f"{adjective}{noun}"

    related_keywords = random.sample(KEYWORDS[category], k=random.randint(2, 4))
    description = f"{category}カテゴリの商品です。{' '.join(related_keywords)}などの特徴があります。状態は写真でご確認ください。\n#Example #{category} {' #'.join(related_keywords)}"

    random_img_id = random.randint(1, 1000)
    image_url = f"https://picsum.photos/id/{random_img_id}/400/300"

    return {
        "name": name,
        "description": description,
        "price": random.randint(5, 500) * 100,
        "image_url": image_url,
        "is_instant_buy_ok": True,  # 取引ロジックで制御するため一旦True
        "seller_id": seller_id,
        "category": category,
        "brand": random.choice(BRANDS),
        "condition": random.choice(CONDITIONS),
        "status": "on_sale",  # 初期値
    }


def seed_data():
    print("Seeding database with Users, Items, and Transactions...")
    db: Session = SessionLocal()

    try:
        # 1. テーブルのリセット (User, Item, Transaction 全て削除・再作成)
        print("Dropping existing tables...")
        Base.metadata.drop_all(bind=engine)
        print("Creating new tables...")
        Base.metadata.create_all(bind=engine)

        # 2. ユーザー作成
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

        # 辞書化してIDでアクセスしやすくする
        user_map = {u.firebase_uid: u for u in created_users}
        user_ids = [u.firebase_uid for u in created_users]

        # 3. 商品と取引の作成
        print(f"Generating {NUM_ITEMS_TO_GENERATE} dummy items...")

        created_items_count = 0
        created_transactions_count = 0

        for _ in range(NUM_ITEMS_TO_GENERATE):
            # ランダムに出品者を選ぶ
            seller_id = random.choice(user_ids)
            item_data = generate_random_item(seller_id)

            # アイテムインスタンス作成
            item = Item(**item_data)

            # 一定確率で「売り切れ」にして取引データを作成
            if random.random() < SOLD_OUT_RATE:
                item.status = "sold"

                # 出品者以外のユーザーを購入者にする
                potential_buyers = [uid for uid in user_ids if uid != seller_id]
                if potential_buyers:
                    buyer_id = random.choice(potential_buyers)

                    # Transaction作成（Itemはまだcommitされていないが、add後に参照可能）
                    transaction = Transaction(
                        item=item,  # itemオブジェクトを直接紐付け
                        buyer_id=buyer_id,
                        price=item.price,
                        created_at=datetime.now()
                        - timedelta(days=random.randint(0, 10)),  # 過去の日付
                    )
                    db.add(transaction)
                    created_transactions_count += 1

            db.add(item)
            created_items_count += 1

        db.commit()

        print(f"Created {created_items_count} items.")
        print(f"Created {created_transactions_count} transactions (SOLD items).")
        print("\nSeeding complete! ✅")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
