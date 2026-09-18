"""
Input validation matching the existing frontend logic.
"""
import re
from datetime import datetime, date


def validate_time(time_str):
    """Check if time matches HH:MM 24-hour format."""
    if not time_str:
        return False
    return bool(re.match(r'^\d{1,2}:\d{2}$', time_str.strip()))


def validate_path_no_spaces(path, filename):
    """Check that path and filename contain no spaces."""
    if path and ' ' in path:
        return False
    if filename and ' ' in filename:
        return False
    return True


def validate_end_date_not_expired(end_date):
    """Check if end date is today or in the future."""
    if not end_date:
        return True  # No end date is valid
    try:
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        return ed >= date.today()
    except Exception:
        return True  # Can't parse = don't block


def deduplicate_key(path, file, time_str):
    """Generate deduplication key for a schedule."""
    return f"{path}/{file}@{time_str}"


def validate_job(job):
    """Validate a job dict and return warning flags.

    Returns dict with timeWarn, spaceWarn, expiredWarn booleans.
    """
    warnings = {
        "timeWarn": not validate_time(job.get("time", "")),
        "spaceWarn": not validate_path_no_spaces(job.get("path", ""), job.get("file", "")),
        "expiredWarn": not validate_end_date_not_expired(job.get("endDate", "")),
    }
    return warnings
