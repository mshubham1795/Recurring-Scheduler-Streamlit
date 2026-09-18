"""
Time and date parsing/conversion utilities.
Ports the JavaScript fixTime(), fixDate() and Python local_to_utc() functions.
"""
import calendar
import logging
from datetime import datetime

log = logging.getLogger("SASBackend")

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
MONTHS_REV = {v: k for k, v in MONTHS.items()}


def fix_time(value):
    """Normalize time strings to 24-hour HH:MM format.

    Handles: AM/PM, Excel decimals (0.625=15:00), HH:MM:SS, H:MM.
    """
    if not value:
        return value
    v = str(value).strip()

    # Check for AM/PM
    has_am = "am" in v.lower()
    has_pm = "pm" in v.lower()
    import re
    clean = re.sub(r'\s*(am|pm)\s*', '', v, flags=re.IGNORECASE).strip()

    # HH:MM or H:MM format
    tm = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', clean)
    if tm:
        h = int(tm.group(1))
        m = int(tm.group(2))
        if has_pm and h < 12:
            h += 12
        if has_am and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"

    # Excel decimal (0.625 = 15:00)
    try:
        n = float(clean)
        if 0 <= n < 1:
            mins = round(n * 1440)
            return f"{mins // 60:02d}:{mins % 60:02d}"
    except ValueError:
        pass

    # Try as date object
    try:
        from datetime import datetime as dt
        d = dt.fromisoformat(v) if "T" in v else None
        if d:
            return f"{d.hour:02d}:{d.minute:02d}"
    except Exception:
        pass

    return v


def fix_date(value):
    """Normalize date strings to YYYY-MM-DD format.

    Handles: YYYY-MM-DD, Excel serial numbers, M/D/YY, M/D/YYYY, D-Mon-YYYY.
    """
    if not value:
        return value
    v = str(value).strip()

    import re

    # Already YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}', v):
        return v[:10]

    # Excel serial number
    try:
        num = float(v)
        if 40000 < num < 60000:
            d = datetime.fromtimestamp((num - 25569) * 86400)
            return d.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # M/D/YY or M/D/YYYY or MM/DD/YY or MM/DD/YYYY
    slash_match = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})$', v)
    if slash_match:
        mo, dy, yr = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
        if yr < 100:
            yr += 2000
        return f"{yr}-{mo:02d}-{dy:02d}"

    # D-Mon-YYYY (e.g., 02-May-2026)
    d_mon_match = re.match(r'^(\d{1,2})[/\-]([A-Za-z]+)[/\-](\d{2,4})$', v)
    if d_mon_match:
        dy = int(d_mon_match.group(1))
        mo_str = d_mon_match.group(2).lower()[:3]
        yr = int(d_mon_match.group(3))
        if yr < 100:
            yr += 2000
        m_num = MONTHS.get(mo_str, 1)
        return f"{yr}-{m_num:02d}-{dy:02d}"

    # Try native parse
    try:
        d = datetime.strptime(v, "%m/%d/%Y")
        return d.strftime("%Y-%m-%d")
    except Exception:
        pass

    try:
        d = datetime.strptime(v, "%d-%b-%Y")
        return d.strftime("%Y-%m-%d")
    except Exception:
        pass

    return v


def local_to_utc(time_str):
    """Convert local time string to UTC for CLUWE's scheduledUTC field.

    Uses the configured TZ_OFFSET_HOURS (IST +5:30 by default) so this
    works correctly on both the local dev machine and on Posit Connect
    (whose server time is UTC).

    Input format: '06-May-2026 10:43:00 AM' (local)
    Output format: '06-May-2026 05:13:00 AM' (UTC)
    """
    from config.constants import TZ_OFFSET_HOURS
    from datetime import timedelta

    try:
        parts = time_str.strip().split()
        date_parts = parts[0].split('-')
        day = int(date_parts[0])
        mon = MONTHS.get(date_parts[1][:3].lower(), 1)
        year = int(date_parts[2])

        time_parts = parts[1].split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        sec = int(time_parts[2]) if len(time_parts) > 2 else 0
        ampm = parts[2].upper() if len(parts) > 2 else ''

        if ampm == 'PM' and hour < 12:
            hour += 12
        elif ampm == 'AM' and hour == 12:
            hour = 0

        local_dt = datetime(year, mon, day, hour, minute, sec)
        # Use configured offset (IST = +5:30) instead of server's local offset
        utc_dt = local_dt - timedelta(hours=TZ_OFFSET_HOURS)

        utc_hour = utc_dt.hour
        utc_ampm = 'PM' if utc_hour >= 12 else 'AM'
        utc_hour_12 = utc_hour % 12 or 12

        mon_str = MONTHS_REV.get(utc_dt.month, 'Jan')

        result = (f"{utc_dt.day:02d}-{mon_str.title()}-{utc_dt.year} "
                  f"{utc_hour_12:02d}:{utc_dt.minute:02d}:{utc_dt.second:02d} {utc_ampm}")
        return result

    except Exception as e:
        log.warning(f"[TIME] Could not convert '{time_str}' to UTC: {e}")
        return time_str


def format_cluwe_time(dt):
    """Format a datetime as CLUWE expects: 'DD-Mon-YYYY HH:MM:SS AM/PM'."""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    h = dt.hour
    ap = 'PM' if h >= 12 else 'AM'
    h = h % 12 or 12
    return (f"{dt.day:02d}-{months[dt.month - 1]}-{dt.year} "
            f"{h:02d}:{dt.minute:02d}:{dt.second:02d} {ap}")
