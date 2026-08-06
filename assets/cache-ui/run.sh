#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8787}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
export HOST PORT REDIS_URL

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install -q -r requirements.txt

echo "Cache State Engine"
echo "  UI:    http://${HOST}:${PORT}"
echo "  Redis: ${REDIS_URL}"
echo "  Bind:  ${HOST} (local only)"
echo ""

exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
