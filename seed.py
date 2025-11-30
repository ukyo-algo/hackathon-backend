import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

# --- .envファイルを読み込む ---
load_dotenv()

# --- 環境変数が読み込まれた後に、DBモジュールをインポートする ---
try:
    # FastAPIアプリ内からのインポートパス (例: uvicorn)
    from app.db.database import SessionLocal, engine, Base
    from app.db.models import User, Item
except ImportError:
    # スクリプトとして直接実行する場合のインポートパス
    from app.db.database import SessionLocal, engine, Base
    from app.db.models import User, Item


# --- ダミーデータの定義 ---

DUMMY_USERS = [
    {
        "firebase_uid": "seed_user_1_uid",
        "username": "Demo User 1 (Seller)",
        "email": "user1@example.com",
        "icon_url": "https://picsum.photos/seed/user1/100/100",
    },
    {
        "firebase_uid": "seed_user_2_uid",
        "username": "Demo User 2 (Buyer)",
        "email": "user2@example.com",
        "icon_url": "https://picsum.photos/seed/user2/100/100",
    },
]

# ↓↓↓ 新しいフィールドを追加した DUMMY_ITEMS リスト ↓↓↓
DUMMY_ITEMS = [
    {
        "name": "おしゃれなTシャツ",
        "description": "古着です。デザインがとてもユニークで、状態も良いです。",
        "price": 1800,
        "image_url": "https://picsum.photos/seed/tshirt/400/300",
        "is_instant_buy_ok": True,
        "seller_id": "seed_user_1_uid",
        "category": "ファッション",
        "brand": "Vintage Select",
        "condition": "目立った傷や汚れなし",
    },
    {
        "name": "レトロなカメラ",
        "description": "動作未確認のジャンク品です。修理できる方、部品取りにどうぞ。",
        "price": 5000,
        "image_url": "https://picsum.photos/seed/camera/400/300",
        "is_instant_buy_ok": False,
        "seller_id": "seed_user_1_uid",
        "category": "家電・スマホ・カメラ",
        "brand": None,
        "condition": "全体的に状態が悪い",
    },
    {
        "name": "使い古したスニーカー",
        "description": "2年ほど履きましたが、まだ使えます。ソールの減り具合は写真を確認してください。",
        "price": 2500,
        "image_url": "https://picsum.photos/seed/sneaker/400/300",
        "is_instant_buy_ok": True,
        "seller_id": "seed_user_2_uid",
        "category": "靴",
        "brand": "Nike",
        "condition": "傷や汚れあり",
    },
    {
        "name": "ゲーミングマウス",
        "description": "1ヶ月ほど使用しました。箱、付属品すべて揃っています。",
        "price": 4200,
        "image_url": "https://picsum.photos/seed/mouse/400/300",
        "is_instant_buy_ok": True,
        "seller_id": "seed_user_1_uid",
        "category": "PC周辺機器",
        "brand": "Logicool",
        "condition": "未使用に近い",
    },
]
# ↑↑↑ DUMMY_ITEMS リストの修正終わり ↑↑↑


def seed_data():
    """
    データベースに初期データを投入する
    """
    print("Seeding database...")

    # データベースセッションを取得
    db: Session = SessionLocal()

    try:
        # --- 1. テーブルの（再）作成 ---
        print("Dropping existing tables...")
        Base.metadata.drop_all(bind=engine)
        print("Creating new tables...")
        Base.metadata.create_all(bind=engine)

        # --- 2. ダミーユーザーの作成 ---
        print("Creating dummy users...")
        created_users = {}
        for user_data in DUMMY_USERS:
            user = User(**user_data)
            db.add(user)
            created_users[user.firebase_uid] = user

        db.commit()
        print(f"Created {len(created_users)} users.")

        # --- 3. ダミー商品の作成 ---
        print("Creating dummy items...")
        created_items = []
        for item_data in DUMMY_ITEMS:
            # Itemモデルのインスタンスを作成 (すべての必要なフィールドを渡す)
            item = Item(
                name=item_data["name"],
                description=item_data["description"],
                price=item_data["price"],
                image_url=item_data["image_url"],
                is_instant_buy_ok=item_data["is_instant_buy_ok"],
                # ↓↓↓ 新しい必須フィールドと任意フィールドを渡す ↓↓↓
                category=item_data["category"],
                brand=item_data["brand"],
                condition=item_data["condition"],
                # ↑↑↑ 新しい必須フィールドと任意フィールドを渡す ↑↑↑
                seller=created_users[item_data["seller_id"]],
            )
            db.add(item)
            created_items.append(item)

        # 商品をコミット
        db.commit()
        print(f"Created {len(created_items)} items.")

        print("\nSeeding complete! ✅")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
        db.rollback()

    finally:
        db.close()
        print("Database session closed.")


# --- スクリプトとして直接実行された場合に seed_data() を呼び出す ---
if __name__ == "__main__":
    seed_data()
