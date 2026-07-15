import isodate
from django import template

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
