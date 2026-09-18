# Recurring Scheduler - Posit Connect Deployment Guide

## Prerequisites

- Python 3.11+
- Posit Connect server with Streamlit support
- `rsconnect-python` CLI tool

## Security Model

**Credentials are NEVER stored on disk or in the database.**

When a user logs in, the app authenticates with CLUWE using HTTP Basic Auth and
receives session cookies (`JSESSIONID` + `XSRF-TOKEN`). Only these opaque session
cookies are held in server memory for background scheduling. A keepalive thread
pings CLUWE every 10 minutes to prevent session timeout.

**Trade-off**: If the Posit Connect process restarts (redeploy, crash, server
reboot), all in-memory sessions are lost. Users must log in again for their
recurring schedules to resume.

## Environment Variables (set in Posit Connect Admin Panel)

| Variable | Required | Description |
|----------|----------|-------------|
| `SCHEDULER_DATA_DIR` | Optional | Directory for SQLite database. Default: `./data/`. Must be writable and persistent across deploys. |
| `SCHEDULER_CLUWE_BASE` | Optional | Override CLUWE base URL. Default: `https://cluwe.am.lilly.com` |

## Deployment Steps

### 1. Install rsconnect-python

```bash
pip install rsconnect-python
```

### 2. Configure Posit Connect server

```bash
rsconnect add --name myserver --server https://your-posit-server.com --api-key YOUR_API_KEY
```

### 3. Deploy

```bash
cd sas_scheduler_streamlit/
rsconnect deploy streamlit --name myserver --title "Recurring Scheduler" .
```

### 4. Post-deploy Configuration

1. Go to Posit Connect Admin → Content → Recurring Scheduler → Settings
2. Set environment variables (if any overrides needed)
3. Under "Runtime": set min processes = 1 (keeps scheduler alive)
4. Under "Access": configure user access permissions

## Important Notes

- **No Credential Storage**: Passwords are never stored. The app holds only CLUWE session cookies in server memory.
- **Data Directory**: Ensure `SCHEDULER_DATA_DIR` points to persistent storage that survives redeployments
- **Min Processes = 1**: This keeps the background scheduler thread and session pool alive even when no users are actively using the app
- **Server Restart**: After a restart, all sessions are lost. Users must log in again for recurring schedules to resume.
- **First Run**: On first deployment, the app auto-creates the SQLite database and migrates any existing `schedules.json`

## Local Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app auto-generates a local encryption key at `data/.encryption_key` for development.
