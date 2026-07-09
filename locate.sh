#!/bin/bash
# HARMATTAN-LOCATE launcher
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

PYTHON="./venv/bin/python"
PIP="./venv/bin/pip"

if [ ! -x "$PYTHON" ]; then
  python3 -m venv venv
fi
if ! "$PYTHON" -c "import flask" 2>/dev/null; then
  "$PIP" install --upgrade pip
  "$PIP" install -r requirements.txt
fi

mkdir -p data
HOST="${HLOC_HOST:-127.0.0.1}"
PORT="${HLOC_PORT:-8095}"
echo "[*] HARMATTAN-LOCATE → http://${HOST}:${PORT}/ops"
echo "[*] Consentement explicite obligatoire — pas de leurre"
exec "$PYTHON" app.py
