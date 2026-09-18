"""
Central constants for Recurring Scheduler (Streamlit Edition).
All CLUWE URLs, drive mappings, color palette, and file paths.
"""
import os
import platform
from pathlib import Path

# ============================================================================
# PLATFORM DETECTION
# ============================================================================
PLATFORM = platform.system()  # "Windows" or "Linux"
IS_POSIT_CONNECT = (
    bool(os.environ.get("RSTUDIO_PRODUCT") == "CONNECT")
    or Path(__file__).resolve().as_posix().startswith("/opt/rstudio-connect")
)
IS_HEADLESS = IS_POSIT_CONNECT or PLATFORM != "Windows"

# ============================================================================
# PATHS -- on Posit Connect (Linux), everything must stay inside APP_DIR
# because the parent directory is read-only.
# Locally (Windows), use parent directory for shared persistence.
# ============================================================================
APP_DIR = Path(__file__).parent.parent  # sas_scheduler_streamlit/

if IS_POSIT_CONNECT or PLATFORM != "Windows":
    PROJECT_DIR = APP_DIR  # On Connect/Linux, APP_DIR is the writable root
else:
    PROJECT_DIR = APP_DIR.parent  # Locally on Windows: Recurring_Scheduler/

SCHEDULES_FILE = PROJECT_DIR / "schedules.json"
AUTH_METHOD_FILE = PROJECT_DIR / "auth_method.json"
LOG_DIR = PROJECT_DIR / "logs"
EXEC_LOG = LOG_DIR / "execution_log.csv"

# ============================================================================
# DATABASE (SQLite) -- env-var override for Posit Connect
# ============================================================================
DB_DIR = Path(os.environ.get("SCHEDULER_DATA_DIR", str(APP_DIR / "data")))
DB_PATH = DB_DIR / "scheduler.db"
ENCRYPTION_KEY_ENV = "SCHEDULER_ENCRYPTION_KEY"

# ============================================================================
# TIMEZONE -- Schedule times are entered in local time (IST).
# On Posit Connect (UTC server), we need the offset to convert correctly.
# Override via SCHEDULER_TZ_OFFSET_HOURS env var if needed.
# ============================================================================
TZ_OFFSET_HOURS = float(os.environ.get("SCHEDULER_TZ_OFFSET_HOURS", "5.5"))  # IST = +5:30

# ============================================================================
# CLUWE API URLs
# ============================================================================
CLUWE_BASE = "https://cluwe.am.lilly.com"
CLUWE_HOME = CLUWE_BASE + "/user/home"
CLUWE_SCHEDULE = CLUWE_BASE + "/user/ajax/computeJobs/schedule"
CLUWE_JOBS = CLUWE_BASE + "/user/ajax/loadComputeJobs"

# ============================================================================
# PATH MAPPING (Windows drive letters -> Linux paths for CLUWE)
# ============================================================================
DRIVE_MAP = {"Z:": "/lillyce", "Y:": "/lillyce", "X:": "/lillyce"}
ARTIFACT_PREFIX = "/ifs/statsclstr1/accesszoneprd"

# ============================================================================
# HTTP / USER AGENT
# ============================================================================
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# ============================================================================
# UI COLOR PALETTE (matches CSS variables from original app)
# ============================================================================
COLOR_PRIMARY = "#C00000"
COLOR_GREEN = "#2E8B57"
COLOR_GREEN_BG = "#E8F5EE"
COLOR_AMBER = "#D48806"
COLOR_AMBER_BG = "#FFF8E6"
COLOR_FAIL = "#CF1322"
COLOR_FAIL_BG = "#FFF1F0"
COLOR_PURPLE = "#6F42C1"
COLOR_PURPLE_BG = "#F4F0FA"
COLOR_BLUE = "#1677B6"
COLOR_BLUE_BG = "#E8F4FD"
COLOR_BG = "#F4F5F7"
COLOR_WHITE = "#FFFFFF"
COLOR_BORDER = "#E0E0E0"
COLOR_TEXT = "#1A1A2E"
COLOR_TEXT2 = "#555555"
COLOR_TEXT3 = "#888888"

# ============================================================================
# SMTP SERVERS (tried in order for email notifications)
# ============================================================================
SMTP_SERVERS = [
    "mailrelay.lilly.com",
    "smtp.lilly.com",
    "relay.lilly.com",
    "mail.lilly.com",
    "localhost",
]
