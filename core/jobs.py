"""
Job submission, status polling, and cancellation for CLUWE Grid.
Multi-user: functions accept explicit session or use per-session auth state.
"""
import json
import time
import logging
from datetime import datetime, timedelta

from core.auth import get_user_auth_state
from core.paths import to_linux, to_artifact
from config.constants import CLUWE_BASE, CLUWE_HOME, CLUWE_SCHEDULE
from utils.time_utils import local_to_utc

log = logging.getLogger("SASBackend")

# CLUWE API URL for loading compute jobs (updated path)
CLUWE_LOAD_JOBS = CLUWE_BASE + "/user/ajax/loadComputeJobs"


def submit_job(linux_path, schedule_time_local=None, send_email=True, cluwe_session=None):
    """Submit a job to CLUWE Grid via POST with XOR-masked CSRF token.

    Args:
        linux_path: Full Linux path to .sas file
        schedule_time_local: Local time string for scheduling
        send_email: Whether to send email notification
        cluwe_session: Explicit CluweSession (used by scheduler). If None, uses current user's session.

    Returns dict with status, message/error, scheduled_time, response.
    """
    if cluwe_session is None:
        state = get_user_auth_state()
        cluwe_session = state.cluwe_session

    if not cluwe_session:
        return {"status": "FAILED", "error": "Not connected. Enter credentials first."}

    artifact = to_artifact(linux_path)

    if schedule_time_local:
        schedule_time_utc = local_to_utc(schedule_time_local)
    else:
        now_utc = datetime.utcnow() + timedelta(seconds=30)
        schedule_time_utc = now_utc.strftime("%d-%b-%Y %I:%M:%S %p")

    log.info(f"[TIME] Local: {schedule_time_local} -> UTC: {schedule_time_utc}")

    payload = [{
        "filePath": linux_path,
        "executionEngine": "SASGrid",
        "jobContext": {"contextId": "1"},
        "artifactPath": artifact,
        "sendEmail": send_email,
        "sendText": False,
        "scheduledUTC": schedule_time_utc,
        "hiddenFromUI": False,
    }]

    # Use XOR-masked XSRF token (Spring Security 6 requirement)
    masked_xsrf = cluwe_session.get_masked_xsrf()
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": masked_xsrf,
        "Origin": CLUWE_BASE,
        "Referer": CLUWE_HOME,
    }

    log.info(f"[SUBMIT] {linux_path} at {schedule_time_utc}")
    log.info(f"[SUBMIT] XSRF masked token length: {len(masked_xsrf)}")

    try:
        r = cluwe_session.post(CLUWE_SCHEDULE, json_data=payload, headers=headers, timeout=30)
        log.info(f"[SUBMIT] HTTP Status: {r.status_code}")
        if r.status_code != 200:
            log.info(f"[SUBMIT] Response body: {r.text[:500]}")

        if r.status_code == 200:
            resp_text = r.text.strip()
            try:
                resp_json = json.loads(resp_text)
                if isinstance(resp_json, dict):
                    if resp_json.get("error") or resp_json.get("status") == "error":
                        return {"status": "FAILED", "error": f"CLUWE error: {resp_text[:500]}",
                                "response": resp_text[:500]}
            except Exception:
                pass

            # Verify job appears
            time.sleep(2)
            verify = get_cluwe_jobs(cluwe_session=cluwe_session)
            if verify.get("status") == "ok":
                job_list = verify.get("jobs", [])
                fn = linux_path.split("/")[-1]
                found = any(fn in str(j.get("filePath", ""))
                            for j in (job_list if isinstance(job_list, list) else []))
                log.info(f"[SUBMIT] Verify: job {'FOUND' if found else 'NOT FOUND'} in CLUWE")

            return {"status": "SUCCESS", "message": f"Scheduled: {linux_path}",
                    "scheduled_time": schedule_time_utc, "response": resp_text[:500]}
        elif r.status_code in (401, 403):
            return {"status": "FAILED", "error": f"Session expired (HTTP {r.status_code}). Login again."}
        else:
            return {"status": "FAILED", "error": f"CLUWE HTTP {r.status_code}: {r.text[:500]}"}
    except Exception as e:
        return {"status": "FAILED", "error": str(e)}


def get_cluwe_jobs(cluwe_session=None):
    """Get job statuses from CLUWE.

    Args:
        cluwe_session: Explicit session. If None, uses current user's session.
    """
    if cluwe_session is None:
        state = get_user_auth_state()
        cluwe_session = state.polling_session or state.cluwe_session

    if not cluwe_session:
        return {"status": "error", "jobs": []}

    masked_xsrf = cluwe_session.get_masked_xsrf()
    ts = str(int(time.time() * 1000))

    h = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": masked_xsrf,
        "Referer": CLUWE_HOME,
    }

    url = CLUWE_LOAD_JOBS + f"?_={ts}"
    try:
        r = cluwe_session.get(url, headers=h, timeout=15)
        if r.status_code == 200 and r.text.strip():
            data = json.loads(r.text)
            job_list = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(job_list, list):
                log.info(f"[JOBS] Got {len(job_list)} jobs from CLUWE")
                return {"status": "ok", "jobs": job_list}
        else:
            log.debug(f"[JOBS] loadComputeJobs: HTTP {r.status_code}")
    except Exception as e:
        log.debug(f"[JOBS] Error: {e}")

    return {"status": "error", "message": "CLUWE job API unavailable."}


def cancel_job(job_id="", file_path="", action="cancel", cluwe_session=None):
    """Cancel or abort a job on CLUWE.

    Args:
        cluwe_session: Explicit session. If None, uses current user's session.

    Returns dict with status and message.
    """
    if cluwe_session is None:
        state = get_user_auth_state()
        cluwe_session = state.cluwe_session

    if not cluwe_session:
        return {"status": "error", "message": "Not connected"}

    masked_xsrf = cluwe_session.get_masked_xsrf()
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": masked_xsrf,
    }

    linux_path = to_linux(file_path) if file_path else ""
    payload = {"jobId": job_id} if job_id else {"filePath": linux_path}

    endpoints = [
        CLUWE_BASE + "/user/ajax/computeJobs/cancel",
        CLUWE_BASE + "/user/ajax/computeJobs/delete",
        CLUWE_BASE + "/user/ajax/computeJobs/remove",
    ]
    if action == "abort":
        endpoints = [
            CLUWE_BASE + "/user/ajax/computeJobs/kill",
            CLUWE_BASE + "/user/ajax/computeJobs/abort",
            CLUWE_BASE + "/user/ajax/computeJobs/cancel",
            CLUWE_BASE + "/user/ajax/computeJobs/delete",
        ]

    for url in endpoints:
        try:
            r = cluwe_session.post(url, json_data=payload, headers=headers, timeout=15)
            log.info(f"[{action.upper()}] {url}: {r.status_code}")
            if r.status_code == 200:
                return {"status": "ok", "message": f"Job {action}led"}
        except Exception as e:
            log.warning(f"[{action.upper()}] {url} failed: {e}")

    # Try array payload
    for url in endpoints[:2]:
        try:
            r = cluwe_session.post(url, json_data=[payload], headers=headers, timeout=15)
            if r.status_code == 200:
                return {"status": "ok", "message": f"Job {action}led"}
        except Exception:
            pass

    return {"status": "error", "message": f"Could not {action} job. It may have already completed."}
