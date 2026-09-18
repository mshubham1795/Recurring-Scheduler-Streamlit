"""
SQLite-based persistence for schedules and execution log.
All queries are scoped by owner_id for multi-user isolation.
Backward-compatible return format (list of dicts) for minimal UI changes.
"""
import logging
from datetime import datetime

from core.database import get_connection, transaction

log = logging.getLogger("SASBackend")


# ============================================================================
# SCHEDULES -- CRUD operations scoped by owner_id
# ============================================================================

def load_schedules(owner_id: int = None) -> list:
    """Load recurring schedules for a specific user (or all if owner_id is None).

    Returns a list of dicts matching the original JSON format:
        [{"study": ..., "path": ..., "file": ..., "time": ..., "freq": ...,
          "days": ..., "endDate": ..., "priority": ..., "active": True/False, "id": ...}, ...]
    """
    conn = get_connection()
    if owner_id is not None:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE owner_id = ? ORDER BY study, time",
            (owner_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM schedules ORDER BY owner_id, study, time"
        ).fetchall()

    return [_row_to_schedule(r) for r in rows]


def load_active_schedules(owner_id: int = None) -> list:
    """Load only active schedules for a user (or all users if None)."""
    conn = get_connection()
    if owner_id is not None:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE owner_id = ? AND active = 1 ORDER BY study, time",
            (owner_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE active = 1 ORDER BY owner_id, study, time"
        ).fetchall()

    return [_row_to_schedule(r) for r in rows]


def load_inactive_schedules(owner_id: int) -> list:
    """Load inactive schedules for a specific user."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM schedules WHERE owner_id = ? AND active = 0 ORDER BY study, time",
        (owner_id,)
    ).fetchall()
    return [_row_to_schedule(r) for r in rows]


def save_schedule(owner_id: int, sched: dict) -> int:
    """Insert or update a single schedule. Returns the schedule ID."""
    conn = get_connection()
    now = datetime.now().isoformat()

    conn.execute("""
        INSERT INTO schedules (owner_id, study, path, file, time, freq, days, end_date, priority, active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(owner_id, path, file, time) DO UPDATE SET
            study = excluded.study,
            freq = excluded.freq,
            days = excluded.days,
            end_date = excluded.end_date,
            priority = excluded.priority,
            active = excluded.active,
            updated_at = excluded.updated_at
    """, (
        owner_id,
        sched.get("study", ""),
        sched.get("path", ""),
        sched.get("file", ""),
        sched.get("time", ""),
        sched.get("freq", "Daily"),
        sched.get("days", ""),
        sched.get("endDate", sched.get("end_date", "")),
        sched.get("priority", "Medium"),
        1 if sched.get("active", True) else 0,
        now, now,
    ))
    conn.commit()

    row = conn.execute(
        "SELECT id FROM schedules WHERE owner_id = ? AND path = ? AND file = ? AND time = ?",
        (owner_id, sched.get("path", ""), sched.get("file", ""), sched.get("time", ""))
    ).fetchone()
    return row[0] if row else None


def save_schedules(owner_id: int, schedules: list):
    """Bulk save/upsert a list of schedules for a user."""
    for s in schedules:
        save_schedule(owner_id, s)
    log.info(f"[SCHED] Saved {len(schedules)} schedule(s) for user_id={owner_id}")


def update_schedule(schedule_id: int, updates: dict):
    """Update specific fields of a schedule by ID."""
    conn = get_connection()
    allowed = {"study", "path", "file", "time", "freq", "days", "end_date", "priority", "active"}
    fields = []
    values = []
    for k, v in updates.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return
    fields.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(schedule_id)

    conn.execute(f"UPDATE schedules SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def deactivate_schedule(schedule_id: int):
    """Deactivate a schedule (soft delete)."""
    update_schedule(schedule_id, {"active": 0})


def reactivate_schedule(schedule_id: int):
    """Reactivate a previously deactivated schedule."""
    update_schedule(schedule_id, {"active": 1})


def delete_schedule(schedule_id: int):
    """Permanently delete a schedule."""
    conn = get_connection()
    conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    conn.commit()


# ============================================================================
# EXECUTION LOG
# ============================================================================

def log_execution(owner_id: int, schedule_id: int = None, study: str = "",
                  file_name: str = "", status: str = "", duration: float = 0,
                  message: str = ""):
    """Log a job execution to the database."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO execution_log (schedule_id, owner_id, study, file_name, status, duration_sec, message, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (schedule_id, owner_id, study, file_name, status, duration, message,
          datetime.now().isoformat()))
    conn.commit()


def get_execution_history(owner_id: int, limit: int = 50) -> list:
    """Get recent execution history for a user."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM execution_log
        WHERE owner_id = ?
        ORDER BY executed_at DESC
        LIMIT ?
    """, (owner_id, limit)).fetchall()
    return [dict(r) for r in rows]


def get_last_execution(schedule_id: int) -> dict:
    """Get the most recent execution for a specific schedule."""
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM execution_log
        WHERE schedule_id = ?
        ORDER BY executed_at DESC
        LIMIT 1
    """, (schedule_id,)).fetchone()
    return dict(row) if row else None


# ============================================================================
# HELPERS
# ============================================================================

def _row_to_schedule(row) -> dict:
    """Convert a SQLite Row to a schedule dict matching the legacy JSON format."""
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "study": row["study"],
        "path": row["path"],
        "file": row["file"],
        "time": row["time"],
        "freq": row["freq"],
        "days": row["days"],
        "endDate": row["end_date"],
        "priority": row["priority"],
        "active": bool(row["active"]),
    }
