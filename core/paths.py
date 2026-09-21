"""
Path conversion utilities for CLUWE Grid.
Converts Windows drive paths to Linux format expected by CLUWE.
Cross-platform: handles both Windows and Linux input paths.
"""
import re
from config.constants import DRIVE_MAP, ARTIFACT_PREFIX, PLATFORM


def to_linux(path):
    """Convert Windows path to Linux format for CLUWE."""
    if not path:
        return path
    path = path.strip()
    if path.startswith("/"):
        return path
    if path.startswith("\\\\"):
        parts = path.replace("\\", "/").lstrip("/").split("/")
        return "/" + "/".join(parts[1:]) if len(parts) >= 2 else path
    drive = path[:2].upper()
    if drive in DRIVE_MAP:
        prefix = DRIVE_MAP[drive]                    # e.g. "/lillyce"
        rest = path[2:].replace("\\", "/")           # e.g. "/ly3002813/..." or "/qa/ly3002813/..."
        linux_path = prefix + rest
        # Ensure /qa/ is present after /lillyce — users sometimes omit it
        if linux_path.startswith("/lillyce/") and not linux_path.startswith("/lillyce/qa/"):
            linux_path = "/lillyce/qa/" + linux_path[len("/lillyce/"):]
        return linux_path
    return path.replace("\\", "/")


def normalize_path(path):
    """Normalize a path for CLUWE submission.
    Handles both Windows and Linux input formats.
    On Linux (Posit Connect): paths are already in /lillyce/... format.
    On Windows: converts drive letters to Linux paths.
    """
    if not path:
        return path
    path = path.strip()
    # Already Linux format
    if path.startswith("/"):
        return path
    # Windows format — convert
    return to_linux(path)


def to_artifact(linux_path):
    """Convert Linux path to CLUWE artifact path."""
    if linux_path.startswith("/lillyce"):
        return ARTIFACT_PREFIX + linux_path
    return linux_path


def extract_study_from_path(fullpath):
    """Extract study name from path using regex pattern _mc_([a-zA-Z]+)."""
    if not fullpath:
        return ""
    norm = fullpath.replace("\\", "/")
    for part in norm.split("/"):
        m = re.match(r".*_mc_([a-zA-Z]+)", part, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return ""
