"""
Inactive Schedules tab -- deactivated schedules with Reactivate/Delete actions.
"""
import streamlit as st
from core.persistence import load_inactive_schedules, reactivate_schedule, delete_schedule


def render():
    """Render the Inactive tab content."""
    owner_id = st.session_state.get("user_id")
    inactive = load_inactive_schedules(owner_id) if owner_id else []

    if not inactive:
        st.markdown('''
        <div class="empty-state">
            <div style="font-size:40px;">🚫</div>
            <h3>No Inactive Schedules</h3>
            <p style="font-size:13px; color:#888;">Deactivated schedules will appear here.</p>
        </div>
        ''', unsafe_allow_html=True)
        return

    st.markdown(f"#### Inactive Schedules ({len(inactive)})")

    # Table header
    header_cols = st.columns([1.5, 3, 1, 1, 1.5, 1, 2])
    headers = ["Study", "Program", "Time", "Frequency", "Days", "End Date", "Actions"]
    for col, h in zip(header_cols, headers):
        col.markdown(f"**{h}**")

    st.divider()

    # Table rows
    for i, sched in enumerate(inactive):
        cols = st.columns([1.5, 3, 1, 1, 1.5, 1, 2])

        with cols[0]:
            st.markdown(f"*{sched.get('study', '')}*")
        with cols[1]:
            fp = (sched.get('path', '') + '/' if sched.get('path') else '') + sched.get('file', '')
            st.write(fp)
        with cols[2]:
            st.write(sched.get('time', ''))
        with cols[3]:
            st.write(sched.get('freq', ''))
        with cols[4]:
            st.write(sched.get('days', '') or '--')
        with cols[5]:
            st.write(sched.get('endDate', '') or '--')
        with cols[6]:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Reactivate", key=f"react_{i}", type="primary"):
                    _reactivate(sched)
            with c2:
                if st.button("Delete", key=f"del_{i}"):
                    st.session_state[f"confirm_del_{i}"] = True
                    st.rerun()

        # Delete confirmation
        if st.session_state.get(f"confirm_del_{i}", False):
            st.warning(f"Permanently delete {sched.get('study', '')}/{sched.get('file', '')}?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, delete", key=f"confirm_yes_{i}", type="primary"):
                    _delete(sched)
            with c2:
                if st.button("Cancel", key=f"confirm_no_{i}"):
                    st.session_state[f"confirm_del_{i}"] = False
                    st.rerun()


def _reactivate(sched):
    """Reactivate a schedule by ID."""
    schedule_id = sched.get("id")
    if schedule_id:
        reactivate_schedule(schedule_id)
    st.toast("Reactivated")
    st.rerun()


def _delete(sched):
    """Permanently delete a schedule by ID."""
    schedule_id = sched.get("id")
    if schedule_id:
        delete_schedule(schedule_id)
    st.toast("Deleted")
    st.rerun()
