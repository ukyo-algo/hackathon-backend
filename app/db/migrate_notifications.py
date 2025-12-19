# hackathon-backend/app/db/migrate_notifications.py
"""
notificationsテーブルのみを作成するマイグレーションスクリプト
既存データを保持したまま新しいテーブルを追加します
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import text
from app.db.database import engine


def create_notifications_table():
    """notificationsテーブルを作成（存在しない場合のみ）"""
    
    create_sql = """
    CREATE TABLE IF NOT EXISTS notifications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        type VARCHAR(50),
        title VARCHAR(255),
        message TEXT,
        link VARCHAR(512),
        is_read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user_id (user_id),
        INDEX idx_is_read (is_read),
        INDEX idx_type (type),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """
    
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            print("Creating notifications table...")
            connection.execute(text(create_sql))
            trans.commit()
            print("✅ notifications table created successfully!")
        except Exception as e:
            trans.rollback()
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    create_notifications_table()
