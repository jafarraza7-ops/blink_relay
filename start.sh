#!/bin/bash
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
PG_BIN=~/Applications/Postgres.app/Contents/Versions/16/bin
PG_DATA=~/pg_blink_data
PG_LOG=~/pg_blink.log
BACKEND="$REPO/backend/backend"
FRONTEND="$REPO/OneDrive_2_20-05-2026"

# ── PostgreSQL ────────────────────────────────────────────────────────────────
if $PG_BIN/pg_ctl -D "$PG_DATA" status &>/dev/null; then
  echo "[postgres] already running"
else
  echo "[postgres] starting..."
  $PG_BIN/pg_ctl -D "$PG_DATA" -l "$PG_LOG" start
  sleep 2
fi

# ── Redis ─────────────────────────────────────────────────────────────────────
if redis-cli ping &>/dev/null; then
  echo "[redis]    already running"
else
  echo "[redis]    starting..."
  redis-server --daemonize yes --logfile /tmp/blink_redis.log --port 6379
  sleep 1
  if redis-cli ping &>/dev/null; then
    echo "[redis]    ready"
  else
    echo "[redis]    ERROR: could not start Redis. Install it with: brew install redis"
    exit 1
  fi
fi

# ── Backend (FastAPI) ─────────────────────────────────────────────────────────
echo "[backend]  starting on http://localhost:8001 ..."
cd "$BACKEND"
.venv311/bin/python -m uvicorn main:app --port 8001 > /tmp/blink_backend.log 2>&1 &
BACKEND_PID=$!

# ── Celery Worker ─────────────────────────────────────────────────────────────
echo "[worker]   starting Celery worker..."
cd "$BACKEND"
.venv311/bin/celery -A app.workers.celery_app worker \
  --loglevel=info \
  -Q default,notifications,jira,reminders \
  > /tmp/blink_worker.log 2>&1 &
WORKER_PID=$!

# ── Celery Beat ───────────────────────────────────────────────────────────────
echo "[beat]     starting Celery beat scheduler..."
cd "$BACKEND"
.venv311/bin/celery -A app.workers.celery_app beat \
  --loglevel=info \
  --pidfile=/tmp/blink_celerybeat.pid \
  --schedule=/tmp/blink_celerybeat.db \
  > /tmp/blink_beat.log 2>&1 &
BEAT_PID=$!

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "[frontend] starting on http://localhost:5173 ..."
cd "$FRONTEND"
npm run dev > /tmp/blink_frontend.log 2>&1 &
FRONTEND_PID=$!

# ── Wait for backend ──────────────────────────────────────────────────────────
echo "[backend]  waiting for startup..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:8001/health &>/dev/null; then
    echo "[backend]  ready — $(curl -s http://localhost:8001/health)"
    break
  fi
  sleep 1
done

# ── Wait for frontend ─────────────────────────────────────────────────────────
echo "[frontend] waiting for startup..."
for i in $(seq 1 15); do
  PORT=$(grep -o 'localhost:[0-9]*' /tmp/blink_frontend.log 2>/dev/null | head -1)
  if [ -n "$PORT" ]; then
    echo "[frontend] ready — http://$PORT"
    break
  fi
  sleep 1
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "Blink Relay is running."
echo "  Backend:  http://localhost:8001  (API docs: http://localhost:8001/docs)"
echo "  Frontend: http://$PORT"
echo "  Worker:   PID $WORKER_PID  (consumes task queues)"
echo "  Beat:     PID $BEAT_PID   (fires scheduled jobs)"
echo ""
echo "Logs:"
echo "  /tmp/blink_backend.log"
echo "  /tmp/blink_worker.log"
echo "  /tmp/blink_beat.log"
echo "  /tmp/blink_frontend.log"
echo "  /tmp/blink_redis.log"
echo ""
echo "Stop all:  kill $BACKEND_PID $WORKER_PID $BEAT_PID $FRONTEND_PID"
echo "           redis-cli shutdown"
echo "           $PG_BIN/pg_ctl -D $PG_DATA stop"
