import isodate
from django import template
from datetime import datetime, timezone
from django.utils.dateparse import parse_datetime

register = template.Library()

@register.filter
def parse_duration(value):
    """ISO 8601 duration string (e.g. PT1M30S) to readable format (e.g. 1:30)"""
    if not value:
        return ""
    try:
        duration = isodate.parse_duration(value)
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    except:
        return value

@register.filter
def format_views(value):
    """視聴回数を1万単位に変換 (10000未満はそのまま、以上は1.0万)"""
    try:
        val = int(value)
        if val < 10000:
            return f"{val}"
        return f"{val / 10000:.1f}万"
    except:
        return value

@register.filter
def relative_time(value):
    """ISO 8601日時を相対時間 (○時間前 / ○日前 / ○年前) に変換"""
    if not value:
        return ""
    try:
        dt = None
        # 1. ISO 8601形式 (2024-05-20T10:00:00Z) を試みる
        try:
            dt = isodate.parse_datetime(value)
        except:
            pass

        # 2. Djangoの標準パーサーで試みる
        if not dt:
            dt = parse_datetime(value.replace('/', '-'))

        # 3. それでもダメなら YYYY-MM-DD 形式として試みる
        if not dt:
            try:
                clean_date = value.split(' ')[0].replace('/', '-')
                dt = datetime.strptime(clean_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except:
                pass

        if not dt:
            return value # どうしても解析できない場合はそのまま表示

        # タイムゾーンを考慮して現在の差分を計算
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        diff = now - dt
        seconds = int(diff.total_seconds())

        if seconds < 3600:
            return f"{max(seconds // 60, 1)}分前"
        if seconds < 86400:
            return f"{seconds // 3600}時間前"
        
        days = diff.days
        if days < 365:
            return f"{days}日前"
        return f"{days // 365}年前"

    except Exception:
        return value
        

