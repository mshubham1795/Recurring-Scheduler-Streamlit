"""
Recurring Schedules tab -- active schedules table with sortable headers and Edit/Deactivate actions.
"""
import streamlit as st
from core.persistence import load_active_schedules, update_schedule, deactivate_schedule


def render():
    """Render the Recurring Schedules tab."""
    owner_id = st.session_state.get("user_id")
    active = load_active_schedules(owner_id) if owner_id else []

    if not active:
        st.markdown('''
        <div class="empty-state">
            <div style="font-size:40px;">📋</div>
            <h3>No Recurring Schedules</h3>
            <p style="font-size:13px; color:#888;">Upload a schedule file and click Save All.</p>
        </div>
        ''', unsafe_allow_html=True)
        return

    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"#### Recurring Schedules ({len(active)})")
    with col2:
        if st.button("🔄 Refresh", key="refresh_recur"):
            st.rerun()

    # Sort state initialization
    if "recur_sort" not in st.session_state:
        st.session_state.recur_sort = "study"
    if "recur_sort_asc" not in st.session_state:
        st.session_state.recur_sort_asc = True

    # Sort schedules based on current sort state
    sort_key = st.session_state.recur_sort
    sort_asc = st.session_state.recur_sort_asc
    active.sort(key=lambda s: str(s.get(sort_key, "")).lower(), reverse=not sort_asc)

    # Clickable sortable table headers
    sort_cols = ["study", "file", "time", "freq", "days", "endDate"]
    header_labels = ["Study", "Program", "Time", "Frequency", "Days", "End Date", "Actions"]

    header_cols = st.columns([1, 2.5, 0.8, 1, 1, 1, 2.7])
    for idx, (col, label) in enumerate(zip(header_cols, header_labels)):
        with col:
            if idx < len(sort_cols):
                # Sortable header — show arrow indicator for active sort column
                sort_field = sort_cols[idx]
                arrow = ""
                if st.session_state.recur_sort == sort_field:
                    arrow = " ▲" if st.session_state.recur_sort_asc else " ▼"
                if st.button(f"{label}{arrow}", key=f"sort_hdr_{sort_field}",
                           type="secondary"):
                    if st.session_state.recur_sort == sort_field:
                        # Toggle direction
                        st.session_state.recur_sort_asc = not st.session_state.recur_sort_asc
                    else:
                        # Change sort column
                        st.session_state.recur_sort = sort_field
                        st.session_state.recur_sort_asc = True
                    st.rerun()
            else:
                st.markdown(f"**{label}**")

    st.divider()

    # Table rows
    for i, sched in enumerate(active):
        cols = st.columns([1, 2.5, 0.8, 1, 1, 1, 2.7])

        with cols[0]:
            st.markdown(f"**{sched.get('study', '')}**")
        with cols[1]:
            fp = (sched.get('path', '') + '/' if sched.get('path') else '') + sched.get('file', '')
            st.markdown(f"`{fp}`")
        with cols[2]:
            st.markdown(f"`{sched.get('time', '')}`")
        with cols[3]:
            st.write(sched.get('freq', ''))
        with cols[4]:
            st.write(sched.get('days', '') or '--')
        with cols[5]:
            st.write(sched.get('endDate', '') or 'No end')
        with cols[6]:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("▶ Run Now", key=f"run_r_{i}", type="primary"):
                    _run_now(sched)
            with c2:
                if st.button("Edit", key=f"edit_r_{i}", type="secondary"):
                    st.session_state[f"editing_{i}"] = True
                    st.rerun()
            with c3:
                if st.button("Deactivate", key=f"deact_r_{i}"):
                    _deactivate(sched)

        # Edit form (inline)
        if st.session_state.get(f"editing_{i}", False):
            _render_edit_form(i, sched)


def _render_edit_form(idx, sched):
    """Render inline edit form for a schedule."""
    st.markdown("---")
    st.markdown(f"**Edit: {sched.get('study', '')} / {sched.get('file', '')}**")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        current_program = (sched.get('path', '') + '/' if sched.get('path') else '') + sched.get('file', '')
        new_program = st.text_input("Program (path/file.sas)", value=current_program,
                                    key=f"edit_program_{idx}")
    with col2:
        new_time = st.text_input("Time (HH:MM)", value=sched.get("time", ""),
                                key=f"edit_time_{idx}")
    with col3:
        freq_options = ["Daily", "Weekly"]
        freq_idx = freq_options.index(sched.get("freq", "Daily")) if sched.get("freq", "Daily") in freq_options else 0
        new_freq = st.selectbox("Frequency", freq_options, index=freq_idx,
                               key=f"edit_freq_{idx}")
    with col4:
        # Days disabled when Daily (only relevant for Weekly)
        if new_freq == "Weekly":
            new_days = st.text_input("Days", value=sched.get("days", ""),
                                    key=f"edit_days_{idx}")
        else:
            new_days = st.text_input("Days", value="", placeholder="N/A (Mon-Fri)",
                                    key=f"edit_days_{idx}", disabled=True)
    with col5:
        new_end = st.text_input("End Date (YYYY-MM-DD)", value=sched.get("endDate", ""),
                               key=f"edit_end_{idx}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save Changes", key=f"save_edit_{idx}", type="primary"):
            import re, os
            if not new_time or not re.match(r'^\d{1,2}:\d{2}$', new_time.strip()):
                st.error("Time must be HH:MM format.")
            elif not new_program.strip():
                st.error("Program path/file is required.")
            else:
                # Parse program back into path and file
                program_stripped = new_program.strip().replace("\\", "/")
                new_file = program_stripped.split("/")[-1] if "/" in program_stripped else program_stripped
                new_path = program_stripped.rsplit("/", 1)[0] if "/" in program_stripped else ""

                schedule_id = sched.get("id")
                if schedule_id:
                    update_schedule(schedule_id, {
                        "path": new_path,
                        "file": new_file,
                        "time": new_time.strip(),
                        "freq": new_freq,
                        "days": new_days.strip(),
                        "end_date": new_end.strip(),
                    })
                st.session_state[f"editing_{idx}"] = False
                st.toast("Schedule updated")
                st.rerun()
    with c2:
        if st.button("Cancel", key=f"cancel_edit_{idx}"):
            st.session_state[f"editing_{idx}"] = False
            st.rerun()
    st.markdown("---")


def _run_now(sched):
    """Immediately submit a saved schedule to CLUWE. Falls back to session pool on expiry."""
    from core.jobs import submit_job
    from core.paths import to_linux
    from core.auth import get_user_auth_state
    from core.user_session import get_session_pool

    file_name = sched.get("file", "")
    if file_name and not file_name.lower().endswith(".sas"):
        file_name += ".sas"
    linux_path = to_linux(sched.get("path", "")).rstrip("/") + "/" + file_name
    with st.spinner(f"Submitting {sched.get('file', '')} to CLUWE..."):
        result = submit_job(linux_path, schedule_time_local=None, send_email=True)

    # If session expired, try the session pool (keepalive may have kept it alive)
    if result.get("status") == "FAILED" and "401" in result.get("error", ""):
        user_id = st.session_state.get("user_id")
        if user_id:
            pool = get_session_pool()
            pool_session = pool.get_session(user_id)
            if pool_session:
                # Update the interactive session state with the pool session
                state = get_user_auth_state()
                state.cluwe_session = pool_session
                with st.spinner("Session refreshed. Retrying..."):
                    result = submit_job(linux_path, schedule_time_local=None, send_email=True)
            else:
                st.warning("Session expired. Please log out and log in again.")

    if result.get("status") == "SUCCESS":
        st.toast(f"✅ {sched.get('study', '')}/{sched.get('file', '')} submitted — executing now!")
    else:
        st.error(f"Failed: {result.get('error', 'Unknown error')}")


def _deactivate(sched):
    """Deactivate a schedule by ID."""
    schedule_id = sched.get("id")
    if schedule_id:
        deactivate_schedule(schedule_id)
    st.toast("Deactivated and moved to Inactive tab")
    st.rerun()
