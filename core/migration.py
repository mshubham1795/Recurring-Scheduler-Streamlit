"""
One-time migration from legacy schedules.json to SQLite.
Runs automatically on first startup if schedules.json exists and the DB is empty.
Idempotent — safe to call multiple times.
"""
import json
import logging
from pathlib import Path
from datetime import datetime

from config.constants import PROJECT_DIR
from core.database import get_connection

log = logging.getLogger("SASBackend")

LEGACY_SCHEDULES = PROJECT_DIR / "schedules.json"


def run_migration():
    """Import legacy schedules.json into SQLite if DB is empty. Idempotent.
    Also renames old frequency values (Weekly->Daily, Custom->Weekly).
    """
    conn = get_connection()

    # Always rename old frequency values to new naming
    _rename_frequencies(conn)

    # Check if schedules table already has data
    count = conn.execute("SELECT COUNT(*) FROM schedules").fetchone()[0]
    if count > 0:
        return  # Already migrated or has user data

    if not LEGACY_SCHEDULES.exists():
        return  # No legacy file to import

    log.info("[MIGRATION] Found legacy schedules.json. Importing...")

    # Create a 'legacy' user to own the imported schedules
    legacy_user_id = _ensure_legacy_user(conn)

    # Read and import schedules
    try:
        schedules = json.loads(LEGACY_SCHEDULES.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"[MIGRATION] Failed to read schedules.json: {e}")
        return

    imported = 0
    for s in schedules:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO schedules
                (owner_id, study, path, file, time, freq, days, end_date, priority, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                legacy_user_id,
                s.get("study", ""),
                s.get("path", ""),
                s.get("file", ""),
                s.get("time", ""),
                s.get("freq", "Daily"),
                s.get("days", ""),
                s.get("endDate", ""),
                s.get("priority", "Medium"),
                1 if s.get("active", True) else 0,
            ))
            imported += 1
        except Exception as e:
            log.warning(f"[MIGRATION] Skipped schedule: {e}")

    conn.commit()
    log.info(f"[MIGRATION] Imported {imported} schedule(s) under 'legacy' user")

    # Rename original file to .bak
    try:
        backup_path = LEGACY_SCHEDULES.with_suffix(".json.bak")
        LEGACY_SCHEDULES.rename(backup_path)
        log.info(f"[MIGRATION] Renamed schedules.json -> {backup_path.name}")
    except Exception as e:
        log.warning(f"[MIGRATION] Could not rename schedules.json: {e}")


def _ensure_legacy_user(conn) -> int:
    """Create or get the 'legacy' user for imported schedules."""
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?", ("legacy",)
    ).fetchone()
    if row:
        return row[0]

    conn.execute(
        "INSERT INTO users (username, email, created_at) VALUES (?, ?, ?)",
        ("legacy", "", datetime.now().isoformat())
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?", ("legacy",)
    ).fetchone()
    return row[0]


def _rename_frequencies(conn):
    """Rename old frequency values to new naming convention.
    Weekly -> Daily, Custom -> Weekly. Idempotent. Skips if already done.
    """
    # Check if there are any old-style values left to rename
    old_count = conn.execute(
        "SELECT COUNT(*) FROM schedules WHERE freq IN ('Weekly', 'Custom')"
    ).fetchone()[0]
    if old_count == 0:
        return  # Already renamed or no old values

    try:
        # Rename "Weekly" to "Daily" (old Weekly = Mon-Fri = new Daily)
        conn.execute("UPDATE schedules SET freq = 'Daily' WHERE freq = 'Weekly'")
        # Rename "Custom" to "Weekly" (old Custom = specific days = new Weekly)
        conn.execute("UPDATE schedules SET freq = 'Weekly' WHERE freq = 'Custom'")
        conn.commit()
        log.info(f"[MIGRATION] Renamed frequency values for {old_count} schedule(s)")
    except Exception as e:
        log.warning(f"[MIGRATION] Could not rename frequencies (will retry next run): {e}")
