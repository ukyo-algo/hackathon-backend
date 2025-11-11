import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# --- .envファイルを読み込む ---
# このスクリプト(seed.py)が `backend` フォルダ直下にあることを想定
# .envファイルから環境変数を読み込み、os.environ にセットする
load_dotenv()

# --- 環境変数が読み込まれた後に、DBモジュールをインポートする ---
# (database.py はインポート時に os.environ を読み込むため、load_dotenv() の後に置く)
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

DUMMY_ITEMS = [
    {
        "name": "おしゃれなTシャツ",
        "description": "古着です。デザインがとてもユニークで、状態も良いです。",
        "price": 1800,
        "image_url": "https://picsum.photos/seed/tshirt/400/300",
        "is_instant_buy_ok": True,
        "seller_id": "seed_user_1_uid",  # User 1が出品
    },
    {
        "name": "レトロなカメラ",
        "description": "動作未確認のジャンク品です。修理できる方、部品取りにどうぞ。",
        "price": 5000,
        "image_url": "https://picsum.photos/seed/camera/400/300",
        "is_instant_buy_ok": False,
        "seller_id": "seed_user_1_uid",  # User 1が出品
    },
    {
        "name": "使い古したスニーカー",
        "description": "2年ほど履きましたが、まだ使えます。ソールの減り具合は写真を確認してください。",
        "price": 2500,
        "image_url": "https://picsum.photos/seed/sneaker/400/300",
        "is_instant_buy_ok": True,
        "seller_id": "seed_user_2_uid",  # User 2が出品
    },
    {
        "name": "ゲーミングマウス",
        "description": "1ヶ月ほど使用しました。箱、付属品すべて揃っています。",
        "price": 4200,
        "image_url": "https://picsum.photos/seed/mouse/400/300",
        "is_instant_buy_ok": True,
        "seller_id": "seed_user_1_uid",  # User 1が出品
    },
]


def seed_data():
    """
    データベースに初期データを投入する
    """
    print("Seeding database...")

    # データベースセッションを取得
    db: Session = SessionLocal()

    try:
        # --- 1. テーブルの（再）作成 ---
        # 開発の初期段階では、毎回テーブルを削除して作り直すのがクリーン
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
            created_users[user.firebase_uid] = user  # 後で使うために保存

        # ユーザーを先にコミット（Itemが参照できるように）
        db.commit()
        print(f"Created {len(created_users)} users.")

        # --- 3. ダミー商品の作成 ---
        print("Creating dummy items...")
        created_items = []
        for item_data in DUMMY_ITEMS:
            # Itemモデルのインスタンスを作成
            item = Item(
                name=item_data["name"],
                description=item_data["description"],
                price=item_data["price"],
                image_url=item_data["image_url"],
                is_instant_buy_ok=item_data["is_instant_buy_ok"],
                # seller_id ではなく、上で作成した User オブジェクトを直接代入
                # これにより、SQLAlchemyが seller_id を自動で設定してくれる
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
        # エラーが発生したら、変更を元に戻す
        db.rollback()

    finally:
        # 成功しても失敗しても、セッションを閉じる
        db.close()
        print("Database session closed.")


# --- スクリプトとして直接実行された場合に seed_data() を呼び出す ---
if __name__ == "__main__":
    seed_data()
