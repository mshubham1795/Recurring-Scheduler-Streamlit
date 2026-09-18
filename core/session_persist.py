"""
Session persistence across browser refreshes.
Uses a process-global session registry (via @st.cache_resource) with tokens
stored in the browser via st.query_params.
"""
import secrets
import threading
from datetime import datetime, timedelta

import streamlit as st


class SessionEntry:
    """A single active session."""
    def __init__(self, username, user_id, cluwe_session=None):
        self.username = username
        self.user_id = user_id
        self.cluwe_session = cluwe_session
        self.polling_session = None
        self.created_at = datetime.now()
        self.last_seen = datetime.now()


class SessionRegistry:
    """Process-global registry of active sessions. Survives page refreshes."""
    def __init__(self):
        self._sessions = {}  # token -> SessionEntry
        self._lock = threading.Lock()

    def create(self, username, user_id, cluwe_session=None) -> str:
        """Create a new session and return the token."""
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = SessionEntry(username, user_id, cluwe_session)
        return token

    def get(self, token) -> SessionEntry | None:
        """Get a session by token. Returns None if expired or invalid."""
        if not token:
            return None
        with self._lock:
            entry = self._sessions.get(token)
            if entry:
                # Expire sessions after 24 hours of inactivity
                if (datetime.now() - entry.last_seen) > timedelta(hours=24):
                    del self._sessions[token]
                    return None
                entry.last_seen = datetime.now()
                return entry
        return None

    def remove(self, token):
        """Remove a session (logout)."""
        with self._lock:
            self._sessions.pop(token, None)

    def cleanup_expired(self):
        """Remove sessions inactive for more than 24 hours."""
        cutoff = datetime.now() - timedelta(hours=24)
        with self._lock:
            expired = [t for t, e in self._sessions.items() if e.last_seen < cutoff]
            for t in expired:
                del self._sessions[t]


@st.cache_resource
def get_session_registry() -> SessionRegistry:
    """Get the process-global session registry (persists across Streamlit reruns)."""
    return SessionRegistry()
