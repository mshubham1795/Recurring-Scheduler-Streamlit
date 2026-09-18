"""
Authentication module for CLUWE Grid.
Multi-user: each browser tab has its own session via st.session_state.
Passwords are NEVER stored. Authenticated sessions are held in-memory
via the SessionPool for background scheduling.
"""
import time
import base64
import logging
import threading
from datetime import datetime

import streamlit as st

from core.http_client import CluweSession
from core.database import get_connection
from core.user_session import get_session_pool
from config.constants import CLUWE_BASE, CLUWE_HOME, CLUWE_SCHEDULE

log = logging.getLogger("SASBackend")


class AuthState:
    """Per-session auth state (stored in st.session_state, NOT shared)."""
    def __init__(self):
        self.cluwe_session = None
        self.polling_session = None
        self.session_user = ""
        self.session_time = None
        self.user_id = None  # database user ID


def get_user_auth_state() -> AuthState:
    """Get the current user's auth state from st.session_state (per-tab)."""
    if "_auth_state" not in st.session_state:
        st.session_state["_auth_state"] = AuthState()
    return st.session_state["_auth_state"]


def is_authenticated() -> bool:
    """Check if the current session is authenticated."""
    state = get_user_auth_state()
    return state.cluwe_session is not None


def get_session_info() -> dict:
    """Get current session info for the logged-in user."""
    state = get_user_auth_state()
    return {
        "connected": state.cluwe_session is not None,
        "polling": state.polling_session is not None,
        "user": state.session_user,
        "user_id": state.user_id,
        "since": state.session_time.isoformat() if state.session_time else "",
    }


def get_or_create_user(username: str) -> int:
    """Get or create a user record in the database. Returns user_id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row:
        user_id = row[0]
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(), user_id)
        )
        conn.commit()
        return user_id

    conn.execute(
        "INSERT INTO users (username, created_at, last_login) VALUES (?, ?, ?)",
        (username, datetime.now().isoformat(), datetime.now().isoformat())
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    return row[0]


def setup_polling_from_session(cluwe_session, auth_state):
    """Try to enable loadComputeJobs polling. Non-critical, short timeouts."""
    masked_xsrf = cluwe_session.get_masked_xsrf()
    ts = str(int(time.time() * 1000))
    h = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": masked_xsrf,
        "Referer": CLUWE_HOME,
    }

    url = CLUWE_BASE + f"/user/ajax/loadComputeJobs?_={ts}"
    try:
        r = cluwe_session.get(url, headers=h, timeout=8)
        log.info(f"[POLL] loadComputeJobs via session: {r.status_code}")
        if r.status_code == 200:
            auth_state.polling_session = cluwe_session
            log.info("[POLL] Polling enabled via authenticated session!")
            return
    except Exception as e:
        log.debug(f"[POLL] Direct: {e}")

    # Try with cloned cookie session
    cookies = cluwe_session.cookies_dict()
    jsid = cookies.get("JSESSIONID", "")
    xsrf_raw = cluwe_session.get_cookie("XSRF-TOKEN")
    if jsid and xsrf_raw:
        try:
            s2 = CluweSession()
            for name, value in cookies.items():
                s2.set_cookie(name, value, "cluwe.am.lilly.com")
            ts2 = str(int(time.time() * 1000))
            masked_xsrf2 = s2.get_masked_xsrf()
            h2 = dict(h)
            h2["X-XSRF-TOKEN"] = masked_xsrf2
            r = s2.get(CLUWE_BASE + f"/user/ajax/loadComputeJobs?_={ts2}",
                       headers=h2, timeout=8)
            log.info(f"[POLL] loadComputeJobs via cloned cookies: {r.status_code}")
            if r.status_code == 200:
                auth_state.polling_session = s2
                log.info("[POLL] Polling enabled via cloned cookies!")
                return
        except Exception as e:
            log.debug(f"[POLL] Cloned: {e}")

    log.info("[POLL] Auto-polling not available. Using timeout fallback.")


def login_cluwe(username, password):
    """Login to CLUWE using basic auth. Per-session (not singleton).

    The password is used ONLY for the initial HTTP Basic Auth handshake.
    It is NEVER stored on disk or in the database.  After login, the
    authenticated CluweSession (with cookies) is registered in the
    in-memory SessionPool so the background scheduler can use it.

    Args:
        username: Lilly ID
        password: Password

    Returns:
        tuple (success: bool, message: str)
    """
    state = get_user_auth_state()
    log.info(f"[AUTH] Logging in as {username}")

    try:
        s = CluweSession()
        creds = base64.b64encode(f"{username}:{password}".encode()).decode()
        auth_headers = {"Authorization": f"Basic {creds}"}
        r = s.get(CLUWE_HOME, headers=auth_headers, timeout=10)
        log.info(f"[AUTH] Basic auth: {r.status_code}")

        if r.status_code == 200 and s.get_cookie("JSESSIONID"):
            # Log all cookies received from CLUWE
            cookies = s.cookies_dict()
            log.info(f"[AUTH] Cookies received: {list(cookies.keys())}")
            log.info(f"[AUTH] XSRF-TOKEN present: {bool(cookies.get('XSRF-TOKEN'))}")
            log.info(f"[AUTH] JSESSIONID present: {bool(cookies.get('JSESSIONID'))}")

            # Verify schedule API is reachable (POST with masked XSRF)
            masked_xsrf = s.get_masked_xsrf()
            h_test = {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-XSRF-TOKEN": masked_xsrf,
                "Content-Type": "application/json",
            }
            try:
                t = s.post(CLUWE_SCHEDULE, json_data=[], headers=h_test, timeout=8)
                log.info(f"[AUTH] Schedule API test: {t.status_code}")
                if t.status_code != 200:
                    log.info(f"[AUTH] Schedule API test response: {t.text[:300]}")
            except Exception as e:
                log.warning(f"[AUTH] Schedule API test failed: {e}")

            # Accept the session
            log.info("[AUTH] Login successful!")
            state.cluwe_session = s
            state.session_user = username
            state.session_time = datetime.now()

            # Create/update user in database
            user_id = get_or_create_user(username)
            state.user_id = user_id

            # Register session in the in-memory pool for background scheduling.
            # No password is stored — the live CluweSession (with cookies)
            # is kept alive by the keepalive thread.
            pool = get_session_pool()
            pool.register_session(user_id, username, s)

            # Run polling setup in background
            threading.Thread(
                target=setup_polling_from_session, args=(s, state), daemon=True
            ).start()

            return True, "Connected to CLUWE"

        elif r.status_code == 503:
            return False, "CLUWE is temporarily unavailable (503). Please try again in a few minutes."
        elif r.status_code == 401:
            return False, "Invalid Lilly ID or password."
        else:
            return False, f"Login failed (HTTP {r.status_code}). Check credentials and try again."

    except Exception as e:
        log.error(f"[AUTH] Connection error: {e}")
        return False, f"Could not connect to CLUWE: {e}"


def login_cookies(jsessionid, xsrf_token):
    """Authenticate using browser-extracted JSESSIONID + XSRF-TOKEN.

    Returns:
        tuple (success: bool, message: str)
    """
    state = get_user_auth_state()

    if not jsessionid or not xsrf_token:
        return False, "Both JSESSIONID and XSRF-TOKEN are required"

    s = CluweSession()
    s.set_cookie("JSESSIONID", jsessionid, "cluwe.am.lilly.com")
    s.set_cookie("XSRF-TOKEN", xsrf_token, "cluwe.am.lilly.com")

    ts = str(int(time.time() * 1000))
    h = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": xsrf_token,
        "Referer": CLUWE_HOME,
    }

    try:
        url = CLUWE_BASE + f"/user/ajax/computeJobs/loadComputeJobs?_={ts}"
        r = s.get(url, headers=h, timeout=10)
        if r.status_code == 200:
            state.cluwe_session = s
            state.polling_session = s
            state.session_user = "cookie-auth"
            state.session_time = datetime.now()
            log.info("[AUTH] Browser cookies verified. Polling session active.")
            return True, "Connected via cookies. Job status polling enabled."
        else:
            return False, f"Cookies invalid (HTTP {r.status_code})"
    except Exception as e:
        return False, str(e)


def logout():
    """Clear the current user's browser session state.

    The in-memory SessionPool session is intentionally KEPT ALIVE so
    that background scheduled jobs continue to run after logout.
    The session is only lost when the server process restarts or when
    the CLUWE session expires and the keepalive ping fails.
    """
    state = get_user_auth_state()
    state.cluwe_session = None
    state.polling_session = None
    state.session_user = ""
    state.session_time = None
    # Note: state.user_id preserved so we know who was logged in
    log.info("[AUTH] User logged out (browser session cleared, pool session kept alive)")
