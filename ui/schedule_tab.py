"""
Schedule tab -- Excel upload, job table, add task form with Browse, save actions.
"""
import os
import re
import threading
import streamlit as st
from io import BytesIO

from utils.excel_parser import parse_upload, create_template_workbook
from utils.validators import deduplicate_key
from core.persistence import load_schedules, save_schedule, save_schedules
from core.paths import to_linux, extract_study_from_path
from ui.components import priority_pill, warning_icon


def render():
    """Render the Schedule tab content."""
    # Info banner
    st.markdown(
        '<div class="info-banner">'
        'Upload your Excel schedule. Define time, days, and optional end date. '
        'The backend will automatically submit jobs to <strong>CLUWE Grid</strong> '
        'at the defined times.</div>',
        unsafe_allow_html=True
    )

    # Check if we have jobs loaded
    if "jobs" not in st.session_state:
        st.session_state.jobs = []

    if not st.session_state.jobs:
        _render_upload_area()
    else:
        _render_job_table()

    # OR separator
    st.markdown(
        '<div style="display:flex; align-items:center; margin:20px 0;">'
        '<div style="flex:1; height:1px; background:#E0E0E0;"></div>'
        '<span style="padding:0 16px; font:600 13px/1 \'Segoe UI\',sans-serif; color:#888;">OR</span>'
        '<div style="flex:1; height:1px; background:#E0E0E0;"></div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Add Task section (always open, no expander)
    _render_add_task()


def _render_upload_area():
    """Render the file upload area — centered and large."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("#### Upload Schedule")
    with col2:
        template_buf = create_template_workbook()
        st.download_button(
            "📥 Download Template",
            data=template_buf.getvalue(),
            file_name="sas_schedule_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_template"
        )

    # Centered, larger upload area
    col_l, col_c, col_r = st.columns([1, 6, 1])
    with col_c:
        uploaded = st.file_uploader(
            "Drop schedule Excel here or click to browse",
            type=["xlsx", "xls", "csv"],
            help="Columns: Study_Name, File_Path, File_Name, Start_Time, Frequency (Weekly/Custom), Days_of_Week, End_Date (optional)",
            key="excel_upload"
        )

        if uploaded:
            try:
                jobs = parse_upload(uploaded)
                st.session_state.jobs = jobs
                st.session_state.upload_filename = uploaded.name
                st.rerun()
            except ValueError as e:
                st.error(f"Upload error: {e}")
            except Exception as e:
                st.error(f"Error reading file: {e}")


def _render_job_table():
    """Render the job table after upload."""
    jobs = st.session_state.jobs
    valid_jobs = [j for j in jobs if not j.get("timeWarn") and not j.get("spaceWarn") and not j.get("expiredWarn")]

    # Header with actions
    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
    with col1:
        st.markdown(f"#### Selected Programs ({len(valid_jobs)} schedulable)")
    with col2:
        if st.button("Save Selected", type="primary", key="save_sel"):
            _save_selected()
    with col3:
        if st.button("Save All", type="primary", key="save_all"):
            _save_all()
    with col4:
        template_buf = create_template_workbook()
        st.download_button("📥 Template", data=template_buf.getvalue(),
                          file_name="sas_schedule_template.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          key="dl_template2")
    with col5:
        if st.button("Close", key="close_jobs"):
            st.session_state.jobs = []
            st.rerun()

    # Select all checkbox
    all_selected = all(st.session_state.get(f"sel_{i}", jobs[i].get("selected", False))
                       for i, j in enumerate(valid_jobs)
                       if not j.get("timeWarn") and not j.get("spaceWarn") and not j.get("expiredWarn")
                       ) if valid_jobs else False
    select_all = st.checkbox("Select all valid", value=all_selected, key="select_all_cb")
    if select_all != all_selected:
        for idx, j in enumerate(jobs):
            if not j.get("timeWarn") and not j.get("spaceWarn") and not j.get("expiredWarn"):
                st.session_state[f"sel_{idx}"] = select_all
        st.rerun()

    # Render table rows
    for i, job in enumerate(jobs):
        blocked = job.get("timeWarn") or job.get("spaceWarn") or job.get("expiredWarn")

        cols = st.columns([0.5, 1.5, 3, 1, 1.5, 1, 1, 1.5])

        with cols[0]:
            if not blocked:
                # Initialize session state for this checkbox if not yet set
                if f"sel_{i}" not in st.session_state:
                    st.session_state[f"sel_{i}"] = job.get("selected", False)
                new_sel = st.checkbox("Select", key=f"sel_{i}", label_visibility="collapsed")
                if new_sel != job.get("selected", False):
                    job["selected"] = new_sel
            else:
                st.markdown("", unsafe_allow_html=True)

        with cols[1]:
            st.markdown(f"**{job['study']}**")

        with cols[2]:
            fp = (job['path'] + '/' if job['path'] else '') + job['file']
            st.markdown(f"`{fp}`")

        with cols[3]:
            warn_html = ""
            if job.get("timeWarn"):
                warn_html = " ⚠️"
            st.markdown(f"`{job['time']}`{warn_html}")

        with cols[4]:
            days_str = f"{job['freq']}"
            if job.get('days'):
                days_str += f" ({job['days']})"
            st.markdown(days_str, unsafe_allow_html=True)

        with cols[5]:
            st.markdown(f"`{job.get('endDate') or 'No end'}`")

        with cols[6]:
            st.markdown(
                f'<span class="pr pr-{job["priority"]}">{job["priority"]}</span>',
                unsafe_allow_html=True
            )

        with cols[7]:
            if blocked:
                reasons = []
                if job.get("timeWarn"):
                    reasons.append("Invalid time")
                if job.get("spaceWarn"):
                    reasons.append("Spaces")
                if job.get("expiredWarn"):
                    reasons.append("Expired")
                st.markdown(f'<span style="color:#CF1322; font-size:11px;">{", ".join(reasons)}</span>',
                          unsafe_allow_html=True)
            else:
                if st.button("Save", key=f"save_one_{i}"):
                    _save_one(job)


def _browse_file():
    """Open file dialog using tkinter (no separate taskbar entry).
    The tkinter root is hidden and kept topmost so the dialog appears
    as a modal overlay rather than a separate window on the taskbar.
    Returns dict with path, file, study, fullpath or None if cancelled.
    """
    selected = [None]

    def open_dialog():
        try:
            import tkinter as tk
            from tkinter import filedialog

            # Create a hidden root window (no taskbar entry)
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            root.attributes('-topmost', True)  # Keep dialog on top
            root.update()  # Force update so attributes take effect

            # Open the file dialog -- it will be modal to the hidden root
            filepath = filedialog.askopenfilename(
                parent=root,
                title="Select .sas File",
                initialdir=os.path.expanduser("~"),
                filetypes=[("SAS Files", "*.sas"), ("All Files", "*.*")]
            )

            if filepath:
                selected[0] = filepath

            root.destroy()
        except Exception:
            pass

    t = threading.Thread(target=open_dialog)
    t.start()
    t.join(timeout=120)

    if not selected[0]:
        return None

    fullpath = selected[0]
    filename = os.path.basename(fullpath)
    dirpath = os.path.dirname(fullpath)
    study = extract_study_from_path(fullpath)

    return {
        "path": dirpath,
        "file": filename,
        "study": study,
        "fullpath": fullpath,
    }


# ---- Server-side file browser (for Posit Connect / headless Linux) --------

_FB_START = "/lillyce"  # Always start here


@st.dialog("Browse Folder", width="small")
def _server_file_browser():
    """Compact scrollable dialog that navigates /lillyce folders.
    Starts at /lillyce (showing prd, qa, etc.) and lets users drill
    down to select a .sas file.
    """
    # Initialize current directory
    if "_fb_current_dir" not in st.session_state:
        st.session_state["_fb_current_dir"] = _FB_START

    current_dir = st.session_state["_fb_current_dir"]

    # Compact header: path + Up button on same row
    h_col1, h_col2 = st.columns([4, 1])
    with h_col1:
        st.caption(current_dir)
    with h_col2:
        parent = os.path.dirname(current_dir)
        can_go_up = (current_dir != _FB_START
                     and parent.startswith(_FB_START)
                     and parent != current_dir)
        if st.button("⬆️", disabled=not can_go_up, key="_fb_up",
                     help="Go to parent folder"):
            st.session_state["_fb_current_dir"] = parent
            st.rerun(scope="fragment")

    # List directory contents
    try:
        entries = list(os.scandir(current_dir))
    except PermissionError:
        st.error(f"⛔ Permission denied")
        return
    except (FileNotFoundError, OSError):
        st.error(f"📂 Directory not found")
        st.session_state["_fb_current_dir"] = _FB_START
        return

    # Separate into directories and .sas files
    dirs = sorted([e for e in entries if e.is_dir(follow_symlinks=True)],
                  key=lambda e: e.name.lower())
    sas_files = sorted([e for e in entries
                        if e.is_file(follow_symlinks=True)
                        and e.name.lower().endswith(".sas")],
                       key=lambda e: e.name.lower())

    if not dirs and not sas_files:
        st.info("No subdirectories or .sas files here.")
        return

    # Scrollable container for folders + files
    with st.container(height=350):
        # Folders — compact single-column list
        for i, d in enumerate(dirs):
            if st.button(f"📁 {d.name}", key=f"_fb_d_{i}",
                         use_container_width=True):
                st.session_state["_fb_current_dir"] = d.path
                st.rerun(scope="fragment")

        # .sas files — primary buttons to stand out
        if sas_files:
            st.divider()
            for i, f in enumerate(sas_files):
                if st.button(f"📄 {f.name}", key=f"_fb_f_{i}",
                             use_container_width=True, type="primary"):
                    dirpath = os.path.dirname(f.path)
                    filename = f.name
                    study = extract_study_from_path(f.path)

                    st.session_state["_browse_path_buf"] = dirpath
                    st.session_state["_browse_file_buf"] = filename
                    st.session_state["_browse_study_buf"] = study or ""
                    st.session_state["_browse_pending"] = True
                    st.session_state.pop("_fb_current_dir", None)
                    st.rerun()


def _render_add_task():
    """Render the Add Task form (always visible, no expander)."""
    # Show success message if a task was just added
    if st.session_state.get("_add_task_success"):
        st.success(st.session_state.pop("_add_task_success"))

    # Clear form fields BEFORE widgets render (avoids StreamlitAPIException)
    if st.session_state.get("_clear_add_form"):
        st.session_state["at_study"] = ""
        st.session_state["at_path"] = ""
        st.session_state["at_file"] = ""
        st.session_state["at_time"] = ""
        st.session_state["at_days"] = ""
        st.session_state["at_freq"] = "Daily"
        st.session_state["at_priority"] = "Medium"
        st.session_state["_clear_add_form"] = False

    st.markdown(
        '<div style="background:#FAFBFC; border:1px solid #E0E0E0; border-radius:6px; '
        'padding:18px; margin-top:4px;">'
        '<span style="font:600 14px/1 \'Segoe UI\',sans-serif; color:#1A1A2E;">➕ Add Task</span>'
        '</div>',
        unsafe_allow_html=True
    )
    st.markdown("")  # small spacing

    # Apply buffered browse results BEFORE widgets render (avoids StreamlitAPIException)
    # The browse result is stored in _browse_result by the Browse button handler,
    # and applied here on the NEXT rerun (before widgets are instantiated).
    if st.session_state.get("_browse_pending"):
        st.session_state["at_path"] = st.session_state.pop("_browse_path_buf", "")
        st.session_state["at_file"] = st.session_state.pop("_browse_file_buf", "")
        study_buf = st.session_state.pop("_browse_study_buf", "")
        if study_buf:
            st.session_state["at_study"] = study_buf
        st.session_state["_browse_pending"] = False

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        study = st.text_input("Study", placeholder="GZQD", key="at_study")
    with col2:
        file_path = st.text_input("File Path", placeholder="/lillyce/qa/...", key="at_path")
    with col3:
        file_name = st.text_input("File Name", placeholder="check.sas", key="at_file")
    with col4:
        freq = st.selectbox("Frequency", ["Daily", "Weekly", "Run Now"], key="at_freq")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        # Time is disabled when "Run Now" is selected
        if freq == "Run Now":
            time_val = st.text_input("Time (HH:MM)", value="", placeholder="N/A (immediate)",
                                     key="at_time", disabled=True)
        else:
            time_val = st.text_input("Time (HH:MM)", placeholder="10:00", key="at_time")
    with col6:
        # Days disabled when Daily or Run Now (only relevant for Weekly)
        if freq == "Weekly":
            days = st.text_input("Days", placeholder="Mon, Wed, Thu", key="at_days")
        else:
            days = st.text_input("Days", value="", placeholder="N/A (Mon-Fri)",
                                 key="at_days", disabled=True)
    with col7:
        end_date = st.date_input("End Date (optional)", value=None, key="at_end")
    with col8:
        # Initialize default only once (session state is sole source of truth)
        if "at_priority" not in st.session_state:
            st.session_state["at_priority"] = "Medium"
        priority = st.selectbox("Priority", ["High", "Medium", "Low"], key="at_priority")

    # Action buttons: Browse + Add Task
    from config.constants import IS_HEADLESS
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])
    with btn_col1:
        if not IS_HEADLESS:
            # Windows/local: show Browse button with native file dialog
            if st.button("📂 Browse", key="browse_btn", type="secondary", use_container_width=True):
                with st.spinner("Opening file picker..."):
                    result = _browse_file()
                if result:
                    # Store in buffer keys -- will be applied on next rerun BEFORE widgets render
                    st.session_state["_browse_path_buf"] = result["path"]
                    st.session_state["_browse_file_buf"] = result["file"]
                    st.session_state["_browse_study_buf"] = result["study"] or ""
                    st.session_state["_browse_pending"] = True
                    st.toast(f"Selected: {result['file']}")
                    st.rerun()
                else:
                    st.toast("No file selected")
        else:
            # Headless/Linux (Posit Connect): server-side file browser dialog
            if st.button("📂 Browse Folder", key="browse_srv_btn", type="secondary",
                         use_container_width=True):
                _server_file_browser()
    with btn_col2:
        if st.button("Add Task", type="primary", key="add_task_btn", use_container_width=True):
            if not file_name:
                st.error("File name is required.")
            elif not study:
                st.error("Study name is required.")
            elif freq == "Run Now":
                # Run Now: submit immediately to CLUWE, don't save to database
                from core.jobs import submit_job
                from core.paths import to_linux
                fn = file_name.strip()
                if fn and not fn.lower().endswith(".sas"):
                    fn += ".sas"
                linux_path = to_linux(file_path.strip()).rstrip("/") + "/" + fn
                with st.spinner("Submitting to CLUWE..."):
                    result = submit_job(linux_path, schedule_time_local=None, send_email=True)
                if result.get("status") == "SUCCESS":
                    st.session_state["_clear_add_form"] = True
                    st.session_state["_add_task_success"] = f"✅ Run Now submitted: {study}/{file_name} — executing now!"
                    st.rerun()
                else:
                    st.error(f"Submission failed: {result.get('error', 'Unknown error')}")
            else:
                # Scheduled (Daily/Weekly): validate time and save to database
                if not time_val or not time_val.strip():
                    st.error("Time is required (HH:MM format) for scheduled tasks.")
                elif not re.match(r'^\d{1,2}:\d{2}$', time_val.strip()):
                    st.error("Time must be HH:MM format (24-hour).")
                else:
                    new_sched = {
                        "study": study.strip(),
                        "path": file_path.strip(),
                        "file": file_name.strip(),
                        "time": time_val.strip(),
                        "freq": freq,
                        "days": days.strip(),
                        "endDate": str(end_date) if end_date else "",
                        "priority": priority,
                        "active": True,
                    }
                    # Save to database (upsert by owner_id + path + file + time)
                    owner_id = st.session_state.get("user_id")
                    if owner_id:
                        save_schedule(owner_id, new_sched)
                    else:
                        save_schedule(1, new_sched)
                    # Flag to clear form on next rerun (before widgets render)
                    st.session_state["_clear_add_form"] = True
                    st.session_state["_add_task_success"] = f"✅ Task added: {study}/{file_name} at {time_val} ({freq})"
                    st.rerun()


def _save_one(job):
    """Save a single job as a recurring schedule."""
    _save_recurring([job])


def _save_selected():
    """Save selected jobs as recurring schedules."""
    jobs = st.session_state.jobs
    selected = [j for i, j in enumerate(jobs)
                if st.session_state.get(f"sel_{i}", j.get("selected", False))
                and not j.get("timeWarn") and not j.get("spaceWarn") and not j.get("expiredWarn")]
    if not selected:
        st.toast("Select jobs first")
        return
    _save_recurring(selected)


def _save_all():
    """Save all valid jobs as recurring schedules."""
    jobs = st.session_state.jobs
    valid = [j for j in jobs if not j.get("timeWarn") and not j.get("spaceWarn") and not j.get("expiredWarn")]
    if not valid:
        st.toast("No valid jobs")
        return
    _save_recurring(valid)


def _save_recurring(job_list):
    """Save a list of jobs as recurring schedules to the database."""
    owner_id = st.session_state.get("user_id") or 1

    new_schedules = [{
        "study": j["study"],
        "path": j["path"],
        "file": j["file"],
        "time": j["time"],
        "freq": j["freq"],
        "days": j.get("days", ""),
        "endDate": j.get("endDate", ""),
        "priority": j.get("priority", "Medium"),
        "active": True,
    } for j in job_list]

    save_schedules(owner_id, new_schedules)
    st.success(f"✅ {len(new_schedules)} recurring schedule(s) saved. Backend will auto-submit at the defined time/day.")
