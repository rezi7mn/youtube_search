import isodate
from django import template
from datetime import datetime, timezone

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
        published_at = isodate.parse_datetime(value)
        now = datetime.now(timezone.utc)
        diff = now - published_at

        hours = int(diff.total_seconds() // 3600)
        if hours < 24:
            return f"{max(hours, 1)}時間前"

        days = int(diff.days)
        if days < 365:
            return f"{days}日前"
        
        years = days // 365
        return f"{years}年前"
    except:
        return value

