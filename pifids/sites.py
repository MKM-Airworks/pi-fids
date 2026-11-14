"""Installation airport and IANA timezone validation."""
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_ZONES = {'SHI': 'Asia/Tokyo', 'ROR': 'Pacific/Palau'}

def airport_code(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Z]{3}', value):
        raise ValueError('Airport must be a three-letter uppercase code')
    return value

def timezone_name(value):
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError('Invalid IANA timezone')
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Invalid IANA timezone') from None
    return value
