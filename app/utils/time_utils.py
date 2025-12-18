# hackathon-backend/app/utils/time_utils.py
"""
日本時間関連のユーティリティ関数
"""

from datetime import datetime, timedelta
from pytz import timezone as tz

JST = tz('Asia/Tokyo')


def get_jst_now() -> datetime:
    """日本時間の現在時刻を取得"""
    return datetime.now(JST)


def get_jst_today():
    """日本時間の今日の日付を取得"""
    return get_jst_now().date()


def to_jst(dt: datetime) -> datetime:
    """日時をJSTに変換"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(JST)
    return JST.localize(dt)


def is_same_day_jst(dt1: datetime, dt2: datetime = None) -> bool:
    """2つの日時が同じ日（JST）かどうか"""
    if dt1 is None:
        return False
    
    if dt2 is None:
        dt2 = get_jst_now()
    
    dt1_jst = to_jst(dt1)
    dt2_jst = to_jst(dt2) if isinstance(dt2, datetime) else dt2
    
    return dt1_jst.date() == (dt2_jst.date() if isinstance(dt2_jst, datetime) else dt2_jst)


def is_consecutive_day_jst(last_dt: datetime) -> bool:
    """前回が昨日かどうか（連続ログイン判定用）"""
    if last_dt is None:
        return False
    
    last_jst = to_jst(last_dt)
    yesterday = get_jst_today() - timedelta(days=1)
    
    return last_jst.date() == yesterday


def days_since_jst(dt: datetime) -> int:
    """指定日時からの経過日数（JST基準）"""
    if dt is None:
        return float('inf')
    
    dt_jst = to_jst(dt)
    today = get_jst_today()
    return (today - dt_jst.date()).days
