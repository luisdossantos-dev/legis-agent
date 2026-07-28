# Rollback Plan

## Quick Rollback (under 5 minutes)

### Docker Deployment
```bash
# Rollback to previous version
docker pull legis-agent-backend:previous
docker stop legis-agent-backend
docker run --rm -d --name legis-agent-backend \
  -p 8000:8000 \
  --env-file ./backend/.env \
  legis-agent-backend:previous
```

### Docker Compose
```bash
# Revert to previous image tag
git checkout <previous-release-tag>
docker compose up -d --build backend
```

### Manual Deployment
```bash
# Revert code and restart
git revert HEAD --no-commit
cd backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Verification Steps

After rollback, verify:
1. `GET /health` returns `{"status": "ok"}`
2. Document upload and listing works
3. Agent analysis returns valid results
4. Email templates endpoint returns 200

## Database

The application uses an in-memory vector store by default (dev mode).
For pgvector production deployments, database rollback requires:
```bash
# Restore from backup
pg_restore -d legisagent /backups/pre-deployment.dump
```

## Monitoring

Watch for these signals during rollback:
- Error rate spikes > 1%
- P95 latency increase > 5s
- Health check failures
