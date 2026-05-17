#!/usr/bin/env bash
# Run the amaca dev stack with the standard local env.
#
#   scripts/dev.sh                backend only (uvicorn, --reload)
#   scripts/dev.sh --frontend     backend + Vite dev server
#   scripts/dev.sh --no-reload    backend without --reload
#
# Backend: http://127.0.0.1:8000   UI: http://localhost:5173
# (use localhost, not 127.0.0.1 — Vite binds IPv6 [::1]).
#
# Env overrides (all optional):
#   VENV                  default ~/.venvs/amaca-dev
#   AMACA_DATA_DIR        default ~/.amaca-local  (DB + job artifacts)
#   AMACA_SESSION_SECRET  default local-dev-persistent-secret
#   AMACA_PORT            default 8000
#   AMACA_CORES_PER_JOB / AMACA_MAX_CONCURRENT_JOBS
#                         if exported, the backend inherits them.
#
# Note: a code-plugin install/upgrade or a CCFLY rebuild needs a full
# restart of this script (plugin discovery runs once at startup).

set -euo pipefail

WITH_FRONTEND=0
RELOAD=--reload
for arg in "$@"; do
  case "$arg" in
    -f|--frontend) WITH_FRONTEND=1 ;;
    --no-reload)   RELOAD= ;;
    -h|--help)     sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

AMACA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$HOME/.venvs/amaca-dev}"
[[ -x "$VENV/bin/uvicorn" ]] || {
  echo "ERROR: $VENV/bin/uvicorn not found — run scripts/setup.sh first." >&2
  exit 1
}

export AMACA_DEV_LOGIN="${AMACA_DEV_LOGIN:-1}"
export AMACA_DATA_DIR="${AMACA_DATA_DIR:-$HOME/.amaca-local}"
export AMACA_SESSION_SECRET="${AMACA_SESSION_SECRET:-local-dev-persistent-secret}"
PORT="${AMACA_PORT:-8000}"

run_backend() {  # $1: foreground|background
  local opts=(amaca.api.app:app --port "$PORT")
  [[ -n "$RELOAD" ]] && opts+=("$RELOAD")
  if [[ "$1" == background ]]; then
    ( cd "$AMACA_DIR" && exec "$VENV/bin/uvicorn" "${opts[@]}" ) &
    BACKEND_PID=$!
  else
    cd "$AMACA_DIR" && exec "$VENV/bin/uvicorn" "${opts[@]}"
  fi
}

echo "==> backend  : http://127.0.0.1:$PORT   (data: $AMACA_DATA_DIR)"

if (( WITH_FRONTEND )); then
  echo "==> frontend : http://localhost:5173"
  run_backend background
  trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT INT TERM
  cd "$AMACA_DIR/frontend"
  [[ -d node_modules ]] || npm install
  npm run dev          # foreground; Ctrl-C stops both (via the trap)
else
  run_backend foreground
fi
