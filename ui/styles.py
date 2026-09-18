"""
Full CSS injection to replicate the original app's visual design.
"""
import streamlit as st


def inject_css():
    """Inject custom CSS to match the original Recurring Scheduler design."""
    st.markdown("""
    <style>
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Root variables */
    :root {
        --pri: #C00000;
        --grn: #2E8B57;
        --grn-bg: #E8F5EE;
        --amb: #D48806;
        --amb-bg: #FFF8E6;
        --fail: #CF1322;
        --fail-bg: #FFF1F0;
        --pur: #6F42C1;
        --pur-bg: #F4F0FA;
        --blue: #1677B6;
        --blue-bg: #E8F4FD;
        --bg: #F4F5F7;
        --white: #FFF;
        --bdr: #E0E0E0;
        --txt: #1A1A2E;
        --t2: #555;
        --t3: #888;
        --rad: 6px;
        --sh: 0 1px 3px rgba(0,0,0,.08);
    }

    /* Status badges */
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-weight: 600;
        font-size: 11px;
        padding: 3px 9px;
        border-radius: 12px;
    }
    .b-Submitted { color: #1677B6; background: #E8F4FD; }
    .b-Active, .b-Running { color: #D48806; background: #FFF8E6; }
    .b-Completed { color: #2E8B57; background: #E8F5EE; }
    .b-Failed { color: #CF1322; background: #FFF1F0; }
    .b-Scheduled { color: #6F42C1; background: #F4F0FA; }
    .b-Cancelled { color: #888; background: #F0F0F0; }

    /* Priority pills */
    .pr { font-weight: 600; font-size: 11px; padding: 2px 7px; border-radius: 10px; }
    .pr-High { color: #C00000; background: #FFF0F0; }
    .pr-Medium { color: #D48806; background: #FFF8E6; }
    .pr-Low { color: #888; background: #F0F0F0; }

    /* Custom table styling */
    .sched-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .sched-table th {
        padding: 9px 12px;
        text-align: left;
        font-weight: 600;
        font-size: 11px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.7px;
        border-bottom: 2px solid #E0E0E0;
        background: #FAFBFC;
        white-space: nowrap;
    }
    .sched-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #F0F0F0;
        vertical-align: middle;
    }
    .sched-table tr:hover td { background: #F8F9FA; }
    .row-past { opacity: 0.5; }

    /* Warning icon */
    .wi { display: inline-block; color: #D48806; cursor: help; font-size: 15px; vertical-align: middle; margin-left: 4px; }
    .wi-fail { color: #CF1322; }

    /* Info banner */
    .info-banner {
        background: #E0F0FF;
        border: 1px solid #B8DAFF;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 16px;
        font-size: 13px;
        color: #004085;
    }

    /* Card styling */
    .card {
        background: #FFF;
        border: 1px solid #E0E0E0;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0,0,0,.08);
        margin-bottom: 18px;
        padding: 18px;
    }

    /* Upload area */
    .upload-zone {
        border: 2px dashed #E0E0E0;
        border-radius: 8px;
        padding: 40px 28px;
        text-align: center;
        transition: all 0.25s;
        background: #FFF;
    }
    .upload-zone:hover { border-color: #C00000; background: #FFF5F5; }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 40px 20px;
        color: #888;
    }
    .empty-state h3 {
        font-weight: 600;
        font-size: 15px;
        color: #1A1A2E;
        margin: 10px 0 4px;
    }

    /* Mono font for paths/times */
    .mono { font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace; }

    /* Popup/success styling */
    .popup-success {
        background: #FFF;
        border: 1px solid #2E8B57;
        border-radius: 10px;
        padding: 28px 36px;
        text-align: center;
    }
    .popup-success h3 { color: #2E8B57; font-weight: 600; font-size: 18px; margin-bottom: 8px; }

    /* Footer */
    .app-footer {
        margin-top: 28px;
        padding: 12px 0;
        border-top: 1px solid #E0E0E0;
        font-family: 'Cascadia Code', 'Consolas', monospace;
        font-size: 11px;
        color: #888;
    }

    /* Streamlit overrides for primary button */
    .stButton > button[kind="primary"] {
        background-color: #C00000;
        border-color: #C00000;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #a00000;
        border-color: #a00000;
    }

    /* Sort header buttons -- look like clickable text headers */
    button[key^="sort_hdr_"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        font-weight: 600 !important;
        font-size: 11px !important;
        color: #555 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        padding: 4px 0 !important;
        cursor: pointer !important;
    }
    button[key^="sort_hdr_"]:hover {
        color: #C00000 !important;
        background: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)
