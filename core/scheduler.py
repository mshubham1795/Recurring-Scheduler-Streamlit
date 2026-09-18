"""
Background scheduler daemon thread for recurring SAS job submission.
Multi-user: queries all active schedules from SQLite, uses per-user sessions.
Uses @st.cache_resource to ensure the thread starts exactly once per server process.
"""
import time
import logging
import threading
from datetime import datetime, timedelta, timezone

import streamlit as st

from core.database import get_connection
from core.user_session import get_session_pool
from core.persistence import log_execution
from core.email_notify import send_session_expiry_notification
from core.paths import to_linux
from core.jobs import submit_job
from config.constants import TZ_OFFSET_HOURS

log = logging.getLogger("SASBackend")

# Process-global in-memory session pool (no passwords stored)
_session_pool = get_session_pool()

# User timezone as a fixed offset (IST = +5:30 by default)
_USER_TZ = timezone(timedelta(hours=TZ_OFFSET_HOURS))


def _now_local():
    """Return current time in the user's timezone (IST by default).
    Works correctly regardless of server timezone (UTC on Posit Connect,
    or local time on Windows dev machine).
    """
    return datetime.now(_USER_TZ)


def should_run_today(sched):
    """Check if a schedule should run today.
    Daily = runs every weekday (Mon-Fri).
    Weekly = runs on specified days only.
    """
    freq = sched.get("freq", "Daily").lower()
    days = sched.get("days", "")
    today = _now_local()
    day_name = today.strftime("%A")
    day_abbr = today.strftime("%a")
    weekday = today.weekday()

    if freq == "daily" or freq == "weekly" and not days:
        # Daily (or Weekly with no specific days) = Mon-Fri
        return weekday < 5
    elif freq == "weekly":
        # Weekly with specific days
        if not days:
            return weekday < 5
        day_list = [d.strip().lower() for d in days.split(",")]
        return day_name.lower() in day_list or day_abbr.lower() in day_list
    # Legacy "custom" values still work
    elif freq == "custom":
        if not days:
            return weekday < 5
        day_list = [d.strip().lower() for d in days.split(",")]
        return day_name.lower() in day_list or day_abbr.lower() in day_list
    return weekday < 5


def _scheduler_loop():
    """Background thread that checks every 15 seconds for recurring jobs across all users."""
    submitted_today = {}
    notified_today = {}  # user_id -> True; prevents spamming expiry emails

    log.info("[SCHED] Multi-user scheduler thread started")

    while True:
        try:
            time.sleep(15)

            now = _now_local()
            today_str = now.strftime("%Y%m%d")

            # Query all active schedules from database (across all users)
            conn = get_connection()
            rows = conn.execute("""
                SELECT s.*, u.username
                FROM schedules s
                JOIN users u ON s.owner_id = u.id
                WHERE s.active = 1
            """).fetchall()

            for row in rows:
                sched = dict(row)
                owner_id = sched["owner_id"]
                schedule_id = sched["id"]

                # Check end date
                end_date = sched.get("end_date", "")
                if end_date:
                    try:
                        ed = datetime.strptime(end_date, "%Y-%m-%d")
                        if now.date() > ed.date():
                            conn.execute(
                                "UPDATE schedules SET active = 0, updated_at = ? WHERE id = ?",
                                (now.strftime("%Y-%m-%dT%H:%M:%S"), schedule_id)
                            )
                            conn.commit()
                            log.info(f"[SCHED] Deactivated expired: {sched.get('file', '')} (end {end_date})")
                            continue
                    except Exception:
                        pass

                # Check if should run today
                if not should_run_today(sched):
                    continue

                # Check time
                sched_time = sched.get("time", "")
                if not sched_time:
                    continue
                try:
                    parts = sched_time.split(":")
                    sched_hour = int(parts[0])
                    sched_min = int(parts[1]) if len(parts) > 1 else 0
                except Exception:
                    continue

                if now.hour != sched_hour or now.minute != sched_min:
                    continue

                # Deduplication key (per user, per file, per time, per day)
                file_key = f"{owner_id}_{sched.get('path', '')}/{sched.get('file', '')}@{sched_time}_{today_str}"
                if file_key in submitted_today:
                    continue

                # Get user's session from in-memory pool (no DB credentials)
                session = _session_pool.get_session(owner_id)
                if not session:
                    log.warning(f"[SCHED] Cannot submit for user_id={owner_id} ({sched.get('username', '')}) - no active session (user must log in)")
                    submitted_today[file_key] = True

                    # Send expiry email once per day per user
                    if owner_id not in notified_today:
                        notified_today[owner_id] = True
                        active_count = len([
                            r for r in rows if dict(r).get("owner_id") == owner_id
                        ])
                        try:
                            send_session_expiry_notification(
                                sched.get("username", ""),
                                active_schedule_count=active_count
                            )
                        except Exception as e:
                            log.debug(f"[SCHED] Expiry email failed for {sched.get('username', '')}: {e}")

                    log_execution(
                        owner_id=owner_id,
                        schedule_id=schedule_id,
                        study=sched.get("study", ""),
                        file_name=sched.get("file", ""),
                        status="FAILED",
                        message="No active session — user must log in"
                    )
                    continue

                # Submit job using the real submit_job function (correct CLUWE payload)
                linux_path = to_linux(sched.get("path", "")).rstrip("/") + "/" + sched.get("file", "")
                sched_dt = datetime(now.year, now.month, now.day, sched_hour, sched_min, 0)
                local_time_str = sched_dt.strftime("%d-%b-%Y %I:%M:%S %p")

                log.info(f"[SCHED] Submitting: {sched.get('username', '')} / {sched.get('study', '')} / {sched.get('file', '')} local={local_time_str}")
                result = submit_job(linux_path, local_time_str, send_email=True, cluwe_session=session)
                log.info(f"[SCHED] Result: {result.get('status', '?')}")

                # On session expiry, remove the dead session from the pool.
                # We cannot re-login (no stored password) — user must log in again.
                if result.get("status") == "FAILED" and "expired" in result.get("error", "").lower():
                    log.warning(f"[SCHED] Session expired for user_id={owner_id}. Removing from pool. User must re-login.")
                    _session_pool.remove_session(owner_id)
                    result = {"status": "FAILED", "error": "Session expired — user must log in again", "duration": 0}

                submitted_today[file_key] = True

                # Log execution to database
                log_execution(
                    owner_id=owner_id,
                    schedule_id=schedule_id,
                    study=sched.get("study", ""),
                    file_name=sched.get("file", ""),
                    status=result.get("status", "UNKNOWN"),
                    duration=result.get("duration", 0),
                    message=result.get("error", result.get("response", ""))[:500]
                )

            # Clear dedup caches at midnight
            if now.hour == 0 and now.minute == 0:
                submitted_today.clear()
                notified_today.clear()

        except Exception as e:
            log.warning(f"[SCHED] Error: {e}")


@st.cache_resource
def _start_scheduler():
    """Start the scheduler thread exactly once per Streamlit server process."""
    thread = threading.Thread(target=_scheduler_loop, daemon=True)
    thread.start()
    log.info("[SCHED] Multi-user scheduler daemon started via cache_resource")
    return thread


def ensure_scheduler_running():
    """Idempotent call to ensure the scheduler is alive."""
    return _start_scheduler()
