"""
Login page with Lilly ID + password form, plus cookie auth alternative.
Credentials are NEVER stored — only the live session is kept in memory.
"""
import streamlit as st
from core import auth
from core.session_persist import get_session_registry


def render_login_page():
    """Render the login page."""
    # Center the login box — narrow width for a clean, premium look
    col1, col2, col3 = st.columns([1.2, 1, 1.2])

    with col2:
        # Red "R" logo
        st.markdown('''
        <div style="text-align:center; margin-bottom:16px;">
            <div style="width:48px; height:48px; background:#C00000; border-radius:10px;
                        display:inline-flex; align-items:center; justify-content:center;
                        color:#fff; font:900 20px 'Segoe UI',sans-serif;">R</div>
        </div>
        ''', unsafe_allow_html=True)

        st.markdown("<h2 style='text-align:center; margin-bottom:6px;'>Recurring Scheduler</h2>",
                    unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center; color:#555; font-size:13px; margin-bottom:20px;'>"
            "Login with your Lilly credentials to access CLUWE Grid.</p>",
            unsafe_allow_html=True
        )

        # Login form
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Lilly ID", placeholder="Starts with L",
                                     key="login_user")
            password = st.text_input("Password", type="password",
                                     placeholder="Password", key="login_pass")

            submitted = st.form_submit_button("Login", type="primary",
                                              use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("Both fields required.")
                else:
                    with st.spinner("Connecting..."):
                        ok, msg = auth.login_cluwe(
                            username.strip(), password
                        )
                    if ok:
                        state = auth.get_user_auth_state()
                        st.session_state.authenticated = True
                        st.session_state.auth_user = username.strip()
                        st.session_state.user_id = state.user_id
                        # Register session for persistence across page refreshes
                        registry = get_session_registry()
                        token = registry.create(
                            username.strip(), state.user_id, state.cluwe_session
                        )
                        st.query_params["session_token"] = token
                        st.toast(f"Connected as {username.strip()}")
                        st.rerun()
                    else:
                        st.error(msg)


@st.dialog("Session Cookies")
def _show_cookie_dialog():
    """Show the cookie authentication dialog."""
    st.caption("F12 > Network > any request > Cookies tab")

    jsid = st.text_input("JSESSIONID", key="cookie_jsid")
    xsrf = st.text_input("XSRF-TOKEN", key="cookie_xsrf")

    if st.button("Connect", type="primary", key="cookie_connect_btn"):
        if not jsid or not xsrf:
            st.error("Both required.")
        else:
            with st.spinner("Validating..."):
                ok, msg = auth.login_cookies(jsid.strip(), xsrf.strip())
            if ok:
                state = auth.get_user_auth_state()
                st.session_state.authenticated = True
                st.session_state.auth_user = "cookie-auth"
                st.session_state.user_id = None
                # Register session for persistence across page refreshes
                registry = get_session_registry()
                token = registry.create("cookie-auth", None, state.cluwe_session)
                st.query_params["session_token"] = token
                st.toast("Connected via cookies")
                st.rerun()
            else:
                st.error(msg)
