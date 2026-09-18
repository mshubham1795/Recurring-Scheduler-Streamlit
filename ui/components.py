"""
Reusable UI components -- HTML snippets for consistent styling.
"""


def status_badge(status):
    """Return HTML for a status badge."""
    return f'<span class="badge b-{status}">{status}</span>'


def priority_pill(priority):
    """Return HTML for a priority indicator."""
    return f'<span class="pr pr-{priority}">{priority}</span>'


def warning_icon(title, fail=False):
    """Return HTML for a warning triangle icon."""
    cls = "wi wi-fail" if fail else "wi"
    return f'<span class="{cls}" title="{title}">&#9888;</span>'


def render_footer():
    """Render the app footer."""
    import streamlit as st
    st.markdown(
        '<div class="app-footer">Recurring Scheduler &middot; CLUWE Grid &middot; Eli Lilly</div>',
        unsafe_allow_html=True
    )
