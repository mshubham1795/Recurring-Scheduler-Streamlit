"""
SAS log file analysis -- checks .log files for ERROR/WARNING lines via CLUWE API.
"""
import logging
from config.constants import CLUWE_BASE

log = logging.getLogger("SASBackend")


def check_sas_log(sas_path, cluwe_session):
    """Fetch and check a SAS log file for errors/warnings.

    Args:
        sas_path: path to the .sas file (will check .log)
        cluwe_session: authenticated CluweSession instance

    Returns:
        dict with status, has_errors, has_warnings, errors list, log_snippet
    """
    if not cluwe_session:
        return {"status": "error", "message": "Not connected"}
    if not sas_path:
        return {"status": "error", "message": "No path"}

    log_path = sas_path.replace(".sas", ".log")
    xsrf = cluwe_session.get_cookie("XSRF-TOKEN")
    headers = {
        "Accept": "text/plain",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": xsrf,
    }

    for url in [
        CLUWE_BASE + f"/user/ajax/fileContent?path={log_path}",
        CLUWE_BASE + f"/user/api/files/content?path={log_path}",
    ]:
        try:
            r = cluwe_session.get(url, headers=headers, timeout=15)
            if r.status_code == 200 and r.text:
                errors = [
                    line.strip() for line in r.text.split("\n")
                    if line.strip().startswith(("ERROR", "WARNING"))
                ]
                has_errors = any(l.startswith("ERROR") for l in errors)
                has_warnings = any(l.startswith("WARNING") for l in errors)
                return {
                    "status": "ok",
                    "has_errors": has_errors,
                    "has_warnings": has_warnings,
                    "errors": errors[:20],
                    "log_snippet": "\n".join(errors[:20]),
                }
        except Exception:
            continue

    return {"status": "error", "message": "Could not read log file"}
