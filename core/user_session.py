"""
In-memory session pool for the background scheduler.
Holds live CluweSession objects (no passwords stored anywhere).
A keepalive thread pings CLUWE periodically to prevent session timeout.

Security: credentials are NEVER written to disk or database.
Trade-off: if the server process restarts, all sessions are lost
and users must log in again.
"""
import time
import logging
import threading
from datetime import datetime

from config.constants import CLUWE_BASE, CLUWE_HOME

log = logging.getLogger("SASBackend")

# How often (seconds) to ping CLUWE to keep sessions alive.
# Typical Java servers time out after 30 min of inactivity;
# pinging every 10 min provides a comfortable margin.
KEEPALIVE_INTERVAL = 600  # 10 minutes


class SessionPool:
    """Process-global pool of authenticated CluweSession objects.

    Sessions are registered at login and kept alive by a background
    heartbeat thread.  The scheduler reads sessions from this pool —
    no database credentials are involved.
    """

    def __init__(self):
        self._sessions = {}   # user_id -> _Entry
        self._lock = threading.Lock()
        self._keepalive_started = False

    # ---- public API --------------------------------------------------------

    def register_session(self, user_id: int, username: str, cluwe_session):
        """Store a live session after successful login.
        Replaces any existing session for the same user_id.
        """
        with self._lock:
            self._sessions[user_id] = _Entry(username, cluwe_session)
            log.info(
                "[POOL] Registered session for %s (user_id=%s). "
                "Pool size: %d", username, user_id, len(self._sessions)
            )
            self._ensure_keepalive()

    def get_session(self, user_id: int):
        """Return the live CluweSession for *user_id*, or None."""
        with self._lock:
            entry = self._sessions.get(user_id)
            if entry and entry.alive:
                return entry.session
        return None

    def remove_session(self, user_id: int):
        """Explicitly remove a session (e.g. session confirmed dead)."""
        with self._lock:
            entry = self._sessions.pop(user_id, None)
            if entry:
                log.info("[POOL] Removed session for %s (user_id=%s)",
                         entry.username, user_id)

    def get_all_user_ids(self) -> list:
        """Return user_ids that currently have a live session."""
        with self._lock:
            return [uid for uid, e in self._sessions.items() if e.alive]

    def has_session(self, user_id: int) -> bool:
        """Check whether a live session exists for user_id."""
        with self._lock:
            entry = self._sessions.get(user_id)
            return entry is not None and entry.alive

    # ---- keepalive ---------------------------------------------------------

    def _ensure_keepalive(self):
        """Start the keepalive thread (once)."""
        if self._keepalive_started:
            return
        self._keepalive_started = True
        t = threading.Thread(target=self._keepalive_loop, daemon=True)
        t.start()
        log.info("[POOL] Keepalive thread started (interval=%ds)", KEEPALIVE_INTERVAL)

    def _keepalive_loop(self):
        """Periodically ping CLUWE for every registered session."""
        while True:
            time.sleep(KEEPALIVE_INTERVAL)
            self._ping_all()

    def _ping_all(self):
        """Send a lightweight request per session to reset the server-side
        inactivity timer.  Dead sessions (401/403) are removed."""
        with self._lock:
            snapshot = list(self._sessions.items())

        for user_id, entry in snapshot:
            if not entry.alive:
                continue
            try:
                ts = str(int(time.time() * 1000))
                masked_xsrf = entry.session.get_masked_xsrf()
                headers = {
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-XSRF-TOKEN": masked_xsrf,
                    "Referer": CLUWE_HOME,
                }
                url = CLUWE_BASE + f"/user/ajax/loadComputeJobs?_={ts}"
                r = entry.session.get(url, headers=headers, timeout=15)

                if r.status_code in (401, 403):
                    log.warning(
                        "[POOL] Session expired for %s (HTTP %d). Removing.",
                        entry.username, r.status_code
                    )
                    entry.alive = False
                    with self._lock:
                        self._sessions.pop(user_id, None)
                    # Notify user via email
                    self._notify_session_expired(user_id, entry.username)
                else:
                    entry.last_ping = datetime.now()
                    log.debug(
                        "[POOL] Keepalive OK for %s (HTTP %d)",
                        entry.username, r.status_code
                    )
            except Exception as e:
                log.debug("[POOL] Keepalive error for %s: %s", entry.username, e)
                # Network blip — don't remove yet; will retry next cycle

    def _notify_session_expired(self, user_id, username):
        """Send an email notification when a session expires."""
        try:
            from core.email_notify import send_session_expiry_notification
            from core.database import get_connection
            conn = get_connection()
            row = conn.execute(
                "SELECT COUNT(*) FROM schedules WHERE owner_id = ? AND active = 1",
                (user_id,)
            ).fetchone()
            count = row[0] if row else 0
            send_session_expiry_notification(username, active_schedule_count=count)
        except Exception as e:
            log.debug("[POOL] Could not send expiry notification for %s: %s",
                      username, e)


class _Entry:
    """Internal bookkeeping for one session."""
    __slots__ = ("username", "session", "alive", "registered_at", "last_ping")

    def __init__(self, username, session):
        self.username = username
        self.session = session
        self.alive = True
        self.registered_at = datetime.now()
        self.last_ping = datetime.now()


# ---------------------------------------------------------------------------
# Process-global singleton (import from anywhere)
# ---------------------------------------------------------------------------
_pool = SessionPool()


def get_session_pool() -> SessionPool:
    """Return the process-global SessionPool singleton."""
    return _pool
