"""
Red brand header with gold accent bar, user info, clock, and logout.
100% Streamlit-native: st.columns() for layout, CSS for red-bar styling.
No JavaScript DOM manipulation. Clock uses JS only for text update.
"""
import streamlit as st


def render_header():
    """One red header row with brand, user ID, logout — all Streamlit-native."""
    auth_user = st.session_state.get("auth_user", "")

    # ── Scoped CSS ──
    # Style the header columns container as a red full-bleed bar.
    # We mark the header with a unique empty div (#hdr-mark) and use CSS :has()
    # to style the parent stHorizontalBlock that contains it.
    st.markdown("""
    <style>
    /* Red background on the columns row containing #hdr-mark */
    [data-testid="stHorizontalBlock"]:has(#hdr-mark) {
        background: #C00000;
        margin: -1rem -1rem 0 -1rem;
        padding: 8px 28px;
        min-height: 50px;
        display: flex;
        align-items: center;
    }

    /* Brand label */
    #hdr-mark {
        font: 700 16px/1 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #fff;
    }

    /* User ID label */
    .hdr-user {
        font: 500 12px/1 'Cascadia Code', 'Consolas', monospace;
        color: rgba(255,255,255,.92);
        white-space: nowrap;
        text-align: right;
    }

    /* Clock label */
    .hdr-clock {
        font: 400 11px/1 'Cascadia Code', 'Consolas', monospace;
        color: rgba(255,255,255,.55);
        text-align: right;
    }

    /* Logout button styled white-on-red */
    [data-testid="stHorizontalBlock"]:has(#hdr-mark) button {
        background: rgba(255,255,255,0.15) !important;
        color: #fff !important;
        border: 1px solid rgba(255,255,255,0.4) !important;
        font-size: 12px !important;
        padding: 6px 16px !important;
        border-radius: 4px !important;
    }
    [data-testid="stHorizontalBlock"]:has(#hdr-mark) button:hover {
        background: rgba(255,255,255,0.3) !important;
        border-color: rgba(255,255,255,0.7) !important;
        color: #fff !important;
    }
    [data-testid="stHorizontalBlock"]:has(#hdr-mark) button:focus {
        box-shadow: none !important;
        color: #fff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Header row: brand | spacer | clock | user | logout ──
    h1, h2, h3, h4 = st.columns([5, 2, 1.5, 1])

    with h1:
        st.markdown('<span id="hdr-mark">Recurring Scheduler</span>',
                    unsafe_allow_html=True)

    with h2:
        st.markdown('<span class="hdr-clock" id="live-clock"></span>',
                    unsafe_allow_html=True)

    with h3:
        st.markdown(f'<span class="hdr-user">&#9679; {auth_user}</span>',
                    unsafe_allow_html=True)

    with h4:
        if st.button("Logout", key="logout_btn", type="secondary"):
            from core.auth import logout
            from core.session_persist import get_session_registry
            logout()
            # Remove session from registry
            token = st.query_params.get("session_token")
            if token:
                get_session_registry().remove(token)
            st.session_state.authenticated = False
            st.session_state.auth_user = ""
            st.session_state.user_id = None
            st.query_params.clear()
            st.rerun()

    # ── Gold accent strip ──
    st.markdown(
        '<div style="height:4px; background:linear-gradient(90deg,#FFD700,#FFA500,#FFD700);'
        ' margin:0 -1rem 0.5rem -1rem;"></div>',
        unsafe_allow_html=True
    )

    # ── Live clock (JS updates text only — no DOM manipulation of widgets) ──
    st.markdown("""
    <script>
        function updateHeaderClock() {
            const el = document.getElementById('live-clock');
            if (el) el.textContent = new Date().toLocaleString('en-IN', {hour12: false});
        }
        updateHeaderClock();
        setInterval(updateHeaderClock, 1000);
    </script>
    """, unsafe_allow_html=True)
