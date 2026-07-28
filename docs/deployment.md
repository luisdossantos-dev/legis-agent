# Deployment & Rollback

> **Project:** Legis Agent — AI-powered legal document analysis desktop app
> **Stack:** Python FastAPI (backend) + React/Tauri (desktop GUI)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Backend Deployment](#backend-deployment)
3. [Frontend / Tauri Build](#frontend--tauri-build)
4. [Rollback Procedures](#rollback-procedures)
5. [Verification](#verification)

---

## Prerequisites

- Git tag or commit SHA identifying the current (working) version
- Docker & Docker Compose (for containerized backend deployment)
- Python 3.12+, Node.js 18+, Rust (for Tauri)

---

## Backend Deployment

### Option A: Docker (recommended for production)

Build and tag the image:

```bash
cd backend
docker build -t legis-agent:latest .
docker tag legis-agent:latest legis-agent:v1.0.0
```

Run with docker-compose:

```bash
# From project root
docker compose up -d backend
```

Run standalone:

```bash
docker run -d \
  --name legis-agent \
  -p 8000:8000 \
  -e LITELLM_API_KEY="sk-..." \
  -e LITELLM_MODEL="openai/gpt-4o" \
  -e VECTOR_STORE_PROVIDER=pgvector \
  legis-agent:latest
```

### Option B: Manual (bare metal / VM)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install --no-cache-dir ".[all]"

# Copy and configure environment
cp .env.example .env
# Edit .env with production values

# Run with process manager (e.g., supervisord, systemd)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Recommended systemd unit (`/etc/systemd/system/legis-agent.service`):

```ini
[Unit]
Description=Legis Agent Backend
After=network.target

[Service]
Type=simple
User=legis
WorkingDirectory=/opt/legis-agent/backend
Environment=PATH=/opt/legis-agent/backend/.venv/bin
ExecStart=/opt/legis-agent/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Frontend / Tauri Build

### React dev server (development)

```bash
cd frontend
npm install
npm run dev          # → http://localhost:1420
```

### Tauri production bundle

```bash
# From project root
cargo tauri build    # → src-tauri/target/release/bundle/
```

The Tauri bundle produces platform-specific installers (`.deb`, `.AppImage`, `.dmg`, `.msi`).

---

## Staging Environment

A staging instance lets you validate changes in a production-like setting before
releasing to users.

### Using Docker Compose

```bash
# Start the staging stack (isolated from dev — different ports, separate DB volume)
docker compose -p legis-staging -f docker-compose.staging.yml up -d

# Verify staging is running
curl -f http://localhost:8001/health
```

The staging stack runs on:

| Service | Port | Dev | Staging |
|---------|------|-----|---------|
| Backend | 8001 | 8000 | 8001 |
| DB | 5433 | 5432 | 5433 |

Key differences from development:
- **No hot-reload** — uses the built image (production-like)
- **`ENVIRONMENT=staging`** — controls debug mode, CORS strictness
- **Isolated DB volume** — `pgdata_staging` keeps staging data separate
- **No local volume mount** — code comes from the image, not your working tree

### Testing against staging

Point the Tauri app or browser to the staging API:

```bash
# Tauri can connect to staging via env var or config
LEGIS_API_URL=http://localhost:8001 cargo tauri dev
```

### Tearing down

```bash
docker compose -p legis-staging -f docker-compose.staging.yml down -v
```

---

## Rollback Procedures

### 1. Docker deployment rollback

**Scenario:** A bad image was deployed and the backend is failing.

**Steps:**

```bash
# 1. Identify the previous working image tag
docker images legis-agent

# 2. Stop and remove the broken container
docker compose stop backend
docker compose rm -f backend

# 3. Retag the previous version as latest
docker tag legis-agent:v1.0.0 legis-agent:latest    # previous known-good

# 4. Restart
docker compose up -d backend

# 5. Verify
curl -f http://localhost:8000/health
```

**If using git tags for versioning:**

```bash
# 1. Checkout the previous release tag
git checkout v1.0.0

# 2. Rebuild
cd backend
docker build -t legis-agent:v1.0.0 .
docker tag legis-agent:v1.0.0 legis-agent:latest

# 3. Restart
cd ..
docker compose up -d backend
```

**Rollback time:** ~2 minutes (assuming image is cached or locally available).

### 2. Manual deployment rollback

**Scenario:** Backend running directly on a server (uvicorn + systemd).

**Steps:**

```bash
# 1. Go to the deployment directory
cd /opt/legis-agent

# 2. Stash any local changes and checkout the previous version
git stash
git checkout v1.0.0    # previous known-good tag

# 3. Rebuild the virtual environment (if dependencies changed)
cd backend
source .venv/bin/activate
pip install --no-cache-dir ".[all]"

# 4. Restart the service
sudo systemctl restart legis-agent

# 5. Verify
curl -f http://localhost:8000/health
sudo journalctl -u legis-agent -n 20 --no-pager
```

**Rollback time:** ~5 minutes (includes pip install if deps changed).

### 3. Tauri desktop app rollback

**Scenario:** A new Tauri release has a critical bug.

**Method A — Tauri built-in updater (if configured):**

1. The auto-updater checks for updates on startup
2. If a bad update was pushed, publish a revert release (previous version) to the update server
3. Users will be prompted to install the revert on next launch

**Method B — Manual reinstall:**

1. Uninstall the current version:
   - **Linux:** `sudo dpkg -r legis-agent` or remove AppImage
   - **macOS:** Drag from Applications to Trash
   - **Windows:** Add/Remove Programs
2. Install the previous version from the releases page

**Method C — Backend-only rollback (for API changes):**

If the frontend is unchanged but the backend was updated, only the backend needs rollback (see Docker or manual procedure above). The Tauri app connects to the backend API and does not require reinstallation for backend rollbacks.

### 4. Database rollback

**Scenario:** A deployment included a schema migration that needs to be reverted.

> **Note:** The current project uses pgvector. Schema changes should always be backward-compatible (additive only). If a destructive migration was applied:

1. Restore from the most recent database backup:
   ```bash
   docker compose exec -T db psql -U user -d legisagent < backup_before_deploy.sql
   ```
2. Then rollback the backend code (see sections above).

**Prerequisite:** Regular database backups should be configured:
```bash
# Example daily backup via cron
0 3 * * * docker compose exec -T db pg_dump -U user -d legisagent > /backups/legisagent_$(date +\%Y\%m\%d).sql
```

---

## Alerting

Alerting ensures you know when the backend is down, slow, or returning errors.

### Built-in health monitor

The project includes a lightweight health monitor at `scripts/health_monitor.py`.
It checks the `/health` endpoint, measures latency, and reports issues via stderr/syslog.

**Single check (for cron / CI / manual):**

```bash
python scripts/health_monitor.py --url http://localhost:8000/health

echo $?
# 0 = healthy
# 1 = degraded (latency > 3s)
# 2 = unhealthy (down, 5xx, timeout)
```

**Daemon mode (for continuous monitoring):**

```bash
python scripts/health_monitor.py --daemon --interval 60
```

### systemd timer (recommended for production)

Create a systemd service and timer to check health every minute:

**`/etc/systemd/system/legis-health-check.service`:**

```ini
[Unit]
Description=Legis Agent Health Check

[Service]
Type=oneshot
ExecStart=/opt/legis-agent/backend/.venv/bin/python /opt/legis-agent/scripts/health_monitor.py
StandardOutput=journal
StandardError=journal
```

**`/etc/systemd/system/legis-health-check.timer`:**

```ini
[Unit]
Description=Run Legis Agent health check every minute

[Timer]
OnCalendar=minutely
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now legis-health-check.timer

# View results
sudo journalctl -u legis-health-check.service -n 10 --no-pager
```

### External uptime monitoring

For production deployments, integrate with an external monitoring service:

| Service | Free tier | Setup |
|---------|-----------|-------|
| [healthchecks.io](https://healthchecks.io) | 20 checks | Ping `/health` every 5 min; alerts on missed pings |
| [Better Uptime](https://betteruptime.com) | 10 monitors | HTTP monitor on the public API URL |
| [Checkly](https://checklyhq.com) | 5 checks | Browser + API checks from multiple regions |
| [Uptime Kuma](https://github.com/louislam/uptime-kuma) | Self-hosted | Docker Compose, push or pull monitoring |

Example cron job with healthchecks.io:

```bash
# In crontab (runs every 5 minutes)
*/5 * * * * curl -fsS --retry 3 https://hc-ping.com/YOUR_UUID > /dev/null
```

### Automatic recovery via systemd

The systemd unit for the backend (see [Backend Deployment](#backend-deployment))
includes `Restart=always`, which automatically restarts the backend if it crashes.
Combined with the health check timer, this provides basic self-healing.

---

## Verification

After any rollback, verify the system is healthy:

```bash
# 1. Health check endpoint
curl -f http://localhost:8000/health

# 2. API responds correctly
curl -f http://localhost:8000/api/v1/system/config

# 3. Check service logs for errors
docker compose logs backend --tail=20    # Docker
sudo journalctl -u legis-agent -n 20     # systemd

# 4. Run smoke tests (if available)
cd backend
pytest tests/test_api.py -v -x
```
