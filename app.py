"""
Recurring Scheduler -- Streamlit Edition
Direct CLUWE Grid API integration with automatic login.
Multi-user support with per-session auth and SQLite persistence.
Session persists across browser refreshes via token-based session registry.

Usage:
    streamlit run app.py
"""
import sys
import logging
from pathlib import Path

# Add the app directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

# Optional: auto-refresh for job status polling (graceful fallback if not installed)
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ============================================================================
# LOGGING SETUP
# ============================================================================
from config.constants import LOG_DIR

LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "backend.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# ============================================================================
# PAGE CONFIG (must be first Streamlit call)
# ============================================================================
st.set_page_config(
    page_title="Recurring Scheduler - CLUWE",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================================
# IMPORTS (after page config)
# ============================================================================
from ui.styles import inject_css
from ui.login import render_login_page
from ui.header import render_header
from ui.schedule_tab import render as render_schedule_tab
from ui.recurring_tab import render as render_recurring_tab
from ui.inactive_tab import render as render_inactive_tab
from ui.components import render_footer
from core.database import ensure_db_ready
from core.scheduler import ensure_scheduler_running
from core.auth import is_authenticated, get_user_auth_state
from core.session_persist import get_session_registry

# ============================================================================
# CUSTOM CSS
# ============================================================================
inject_css()

# ============================================================================
# DATABASE INITIALIZATION (creates tables + migrates legacy data on first run)
# ============================================================================
ensure_db_ready()

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "auth_user" not in st.session_state:
    st.session_state.auth_user = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "jobs" not in st.session_state:
    st.session_state.jobs = []
if "upload_filename" not in st.session_state:
    st.session_state.upload_filename = ""

# ============================================================================
# SESSION RESTORE ON PAGE REFRESH
# If not authenticated in session_state, check if there's a valid token
# in query params that maps to an active session in the process-global registry.
# ============================================================================
if not st.session_state.authenticated:
    registry = get_session_registry()
    params = st.query_params
    token = params.get("session_token", None)
    if token:
        entry = registry.get(token)
        if entry:
            # Restore session from registry
            st.session_state.authenticated = True
            st.session_state.auth_user = entry.username
            st.session_state.user_id = entry.user_id
            # Restore the auth state object
            auth_state = get_user_auth_state()
            auth_state.cluwe_session = entry.cluwe_session
            auth_state.polling_session = entry.polling_session
            auth_state.session_user = entry.username
            auth_state.user_id = entry.user_id

# ============================================================================
# START BACKGROUND SCHEDULER (idempotent -- runs once per server process)
# ============================================================================
ensure_scheduler_running()

# ============================================================================
# MAIN APP LOGIC
# ============================================================================
if not st.session_state.authenticated:
    # Show login page
    render_login_page()
else:
    # Show main application
    render_header()

    # Auto-refresh every 30 seconds for job status polling
    if HAS_AUTOREFRESH:
        st_autorefresh(interval=30000, limit=None, key="auto_refresh")

    # Tab navigation
    tab1, tab2, tab3 = st.tabs(["📅 Schedule", "🔄 Recurring Schedules", "⏸️ Inactive"])

    with tab1:
        render_schedule_tab()

    with tab2:
        render_recurring_tab()

    with tab3:
        render_inactive_tab()

    # Footer
    render_footer()
