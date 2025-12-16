# hackathon-backend/app/db/seed.py
RARITY_LABELS = {
    1: "ノーマル",
    2: "レア",
    3: "スーパーレア",
    4: "ウルトラレア",
    5: "チャンピョン",
}
import os
import random
import sys
from sqlalchemy.orm import Session
from sqlalchemy import text, MetaData  # MetaDataとtextを追加

# 自身の場所(app/db)から2つ上(プロジェクトルート)に戻ってパスを通す
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

# .envがなくてもGCP環境変数があれば動作します
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from app.db.database import SessionLocal, engine, Base
    from app.db.models import (
        User,
        Item,
        Like,
        Comment,
        AgentPersona,
        UserPersona,
    )

    # 作成したデータファイルからインポート
    from app.db.data.personas import PERSONAS_DATA
    from app.db.data.items import REALISTIC_ITEMS
except ImportError as e:
    print(f"Import Error in seed.py: {e}")
    # 直接実行で失敗しないようexitする
    sys.exit(1)

from app.db.data.image_urls import UNSPLASH_IMAGE_URLS


def _get_product_image_url(category: str) -> str:
    """カテゴリに応じてUnsplashの画像URLを返す"""
    urls = UNSPLASH_IMAGE_URLS.get(category, UNSPLASH_IMAGE_URLS["デフォルト"])
    return random.choice(urls)


def _build_demo_image_url(relative_url: str) -> str:
    """デモ画像のパスを絶対URLに変換する"""
    FRONTEND_URL = os.getenv("FRONTEND_URL")
    if not relative_url.startswith("/"):
        return relative_url
    return f"{FRONTEND_URL}{relative_url}"


def create_initial_data(db: Session):
    """実際にデータを投入する共通ロジック"""

    # 1. キャラクター投入
    print("🤖 Creating Agent Personas...")
    persona_objects = {}
    for p_data in PERSONAS_DATA:
        persona = AgentPersona(
            id=p_data["id"],
            name=p_data["name"],
            description=p_data["description"],
            system_prompt=p_data["system_prompt"],
            avatar_url=p_data["avatar_url"],
            rarity=p_data["rarity"],
            theme_color=p_data["theme_color"],
            rarity_name=p_data["rarity_name"],
            # rarity_keyは不要
        )
        db.add(persona)
        persona_objects[p_data["id"]] = persona
    db.commit()

    # 2. テストユーザー投入
    print("👤 Creating Users...")
    users_config = [
        {"uid": "uid_1", "name": "TechLover", "email": "tech@test.com"},
        {"uid": "uid_2", "name": "Fashionista", "email": "fashion@test.com"},
        {"uid": "uid_3", "name": "Beginner", "email": "beg@test.com"},
        # ★ 全キャラ解放済みユーザーを追加
        {
            "uid": "uid_master",
            "name": "MasterUser",
            "email": "master@test.com",
            "all_personas": True,
        },
    ]
    created_users = []
    for u_conf in users_config:
        user = User(
            firebase_uid=u_conf["uid"],
            username=u_conf["name"],
            email=u_conf["email"],
            current_persona_id=1,
        )
        db.add(user)
        db.flush()  # IDを確定させる

        if u_conf.get("all_personas"):
            # 全キャラ所持
            for p in persona_objects.values():
                up = UserPersona(
                    user_id=user.id,
                    persona_id=p.id,
                    stack_count=1,
                )
                db.add(up)
        else:
            # 通常ユーザーはデフォルトキャラ(ID:1)のみ所持
            if 1 in persona_objects:
                up = UserPersona(user_id=user.id, persona_id=1, stack_count=1)
                db.add(up)

        created_users.append(user)
    db.commit()

    # 3. リアルな商品データの投入
    print("📦 Creating Items (Realistic Data)...")
    user_uids = [u.firebase_uid for u in created_users]

    for item_data in REALISTIC_ITEMS:
        seller_uid = random.choice(user_uids)

        # image_url が既に指定されている場合（デモ画像）は絶対URLへ変換
        if "image_url" in item_data:
            image_url = _build_demo_image_url(item_data["image_url"])
            print(f"using_{image_url}")
        else:
            # 未指定の場合は Unsplash から自動割り当て
            image_url = _get_product_image_url(item_data["category"])

        item = Item(
            name=item_data["name"],
            description=item_data["description"],
            price=item_data["price"],
            category=item_data["category"],
            brand=item_data["brand"],
            condition=item_data["condition"],
            image_url=image_url,
            is_instant_buy_ok=True,
            status="on_sale",
            seller_id=seller_uid,
        )

        # ランダムエンゲージメント
        for uid in user_uids:
            if uid != seller_uid and random.random() < 0.2:
                db.add(Like(user_id=uid, item=item))
                if random.random() < 0.3:
                    db.add(
                        Comment(
                            user_id=uid, item=item, content="購入を検討しています。"
                        )
                    )
        db.add(item)

    db.commit()
    print("✨ Seeding complete!")


# --- メインロジック 1: アプリ起動時用 ---
def seed_if_empty(db: Session):
    """DBが空の場合のみシードを実行する"""
    try:
        if db.query(AgentPersona).count() == 0:
            print("🚀 DB is empty. Seeding initial data...")
            create_initial_data(db)
        else:
            print("ℹ️ Data already exists. Skipping seed.")
    except Exception as e:
        print(f"⚠️ Seed check failed: {e}")
        db.rollback()


def reset_and_seed():
    """
    テーブルを全削除して再作成し、データを投入する。
    コードにない古いテーブルも削除するため、外部キーチェックを無効化して全削除を行う。
    """
    print("💥 FORCE RESETTING DATABASE...")

    # エンジンから直接接続を取得
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            # 1. 外部キーチェックを無効化 (これで依存関係を無視して削除できる)
            print("   -> Disabling foreign key checks...")
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))

            # 2. 現在DBにある全テーブルをリフレクション(取得)して削除
            #    これなら 'user_personas' のような亡霊テーブルも認識して消せる
            print("   -> Reflecting and dropping all tables...")
            metadata = MetaData()
            metadata.reflect(bind=connection)
            metadata.drop_all(bind=connection)

            # 3. 新しい定義でテーブル作成
            print("   -> Creating all tables...")
            Base.metadata.create_all(bind=connection)

            # 4. 外部キーチェックを戻す
            print("   -> Re-enabling foreign key checks...")
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

            trans.commit()
            print("✅ Database reset successful.")

        except Exception as e:
            trans.rollback()
            print(f"❌ DB Reset Error: {e}")
            return

    # データ投入はSessionで行う
    db = SessionLocal()
    try:
        create_initial_data(db)
    finally:
        db.close()


if __name__ == "__main__":
    # 直接実行された場合は、強制リセットを行う
    reset_and_seed()
