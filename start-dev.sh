#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/.local/logs"
PID_FILE="$ROOT_DIR/.local/web.pid"
mkdir -p "$LOG_DIR"

cd "$ROOT_DIR"
docker network inspect ai >/dev/null 2>&1 || docker network create ai
APP_ENV=dev docker compose up -d

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  kill "$(cat "$PID_FILE")" 2>/dev/null || true
fi

cd "$ROOT_DIR/web"
VITE_APP_ENV=dev nohup npm run dev </dev/null >>"$LOG_DIR/web-dev.log" 2>&1 &
echo $! >"$PID_FILE"

echo "Środowisko DEV uruchomione (Docker Compose + web PID: $(cat "$PID_FILE"))."
