"""
Email notification via SMTP for job completion alerts and session expiry warnings.
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from config.constants import SMTP_SERVERS

log = logging.getLogger("SASBackend")


def send_notification(recipient, file_name, status, error_msg="", session_user=""):
    """Send email notification about job completion.

    Returns dict with status and message.
    """
    if not recipient:
        return {"status": "skipped", "message": "No email configured"}

    if status == "Completed":
        subject = f"[Recurring Scheduler] {file_name} - Execution Completed Successfully"
        body = f"{file_name} execution completed successfully."
    elif status == "CompletedWithWarning":
        subject = f"[Recurring Scheduler] {file_name} - Completed with Exception"
        body = (f"{file_name} execution completed with an exception or error in the log, "
                f"please check.\n\nLog excerpt:\n{error_msg[:1000]}")
    elif status == "Failed":
        subject = f"[Recurring Scheduler] {file_name} - Execution Failed"
        body = f"{file_name} execution failed.\n\nError:\n{error_msg[:1000]}"
    else:
        subject = f"[Recurring Scheduler] {file_name} - Status: {status}"
        body = f"{file_name} status: {status}\n\n{error_msg[:1000]}"

    smtp_servers = [os.environ.get("SMTP_SERVER", "")] + SMTP_SERVERS
    smtp_port = int(os.environ.get("SMTP_PORT", "25"))
    email_from = os.environ.get("EMAIL_FROM", f"{session_user}@lilly.com")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = recipient

    for server in smtp_servers:
        if not server:
            continue
        try:
            with smtplib.SMTP(server, smtp_port, timeout=5) as s:
                s.send_message(msg)
            log.info(f"[EMAIL] Sent via {server} to {recipient}: {subject}")
            return {"status": "ok", "message": f"Email sent to {recipient}"}
        except Exception:
            continue

    log.debug("[EMAIL] Could not send (no SMTP server reachable)")
    return {"status": "skipped", "message": "SMTP unavailable. CLUWE sends its own completion emails."}


def send_session_expiry_notification(username, active_schedule_count=0):
    """Send email to a user when their CLUWE session has expired.

    Tells the user to log in again so their recurring schedules can resume.

    Args:
        username: Lilly ID (used to derive email as {username}@lilly.com)
        active_schedule_count: Number of active schedules affected

    Returns dict with status and message.
    """
    if not username or username == "cookie-auth":
        return {"status": "skipped", "message": "No username for email"}

    recipient = f"{username}@lilly.com"
    subject = "[Recurring Scheduler] Session Expired — Login Required"

    schedule_info = ""
    if active_schedule_count > 0:
        schedule_info = (
            f"\nYou have {active_schedule_count} active recurring schedule(s) "
            f"that will NOT execute until you log in again.\n"
        )

    body = (
        f"Hi {username},\n\n"
        f"Your CLUWE session for the Recurring Scheduler has expired.{schedule_info}\n"
        f"Please log in to the Recurring Scheduler app to restore your session "
        f"and resume background job execution.\n\n"
        f"Why did this happen?\n"
        f"  - The server may have been restarted (redeployment or maintenance)\n"
        f"  - CLUWE may have been temporarily unavailable\n"
        f"  - The session may have timed out due to an extended CLUWE outage\n\n"
        f"Your schedules are still saved and will resume automatically once you log in.\n\n"
        f"— Recurring Scheduler"
    )

    smtp_servers = [os.environ.get("SMTP_SERVER", "")] + SMTP_SERVERS
    smtp_port = int(os.environ.get("SMTP_PORT", "25"))
    email_from = os.environ.get("EMAIL_FROM", f"{username}@lilly.com")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = recipient

    for server in smtp_servers:
        if not server:
            continue
        try:
            with smtplib.SMTP(server, smtp_port, timeout=5) as s:
                s.send_message(msg)
            log.info(f"[EMAIL] Session expiry notification sent to {recipient} via {server}")
            return {"status": "ok", "message": f"Expiry notification sent to {recipient}"}
        except Exception:
            continue

    log.debug(f"[EMAIL] Could not send session expiry notification to {recipient} (no SMTP reachable)")
    return {"status": "skipped", "message": "SMTP unavailable"}
