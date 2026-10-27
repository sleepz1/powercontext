#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  uv venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv pip install -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Ensure sample starts buggy
bash "$ROOT/scripts/reset.sh" >/dev/null

# Health checks
curl --fail --silent --show-error "$POWERCONTEXT_URL/health/live" >/dev/null \
  || curl --fail --silent --show-error http://127.0.0.1:8000/health/live >/dev/null

export PYTHONPATH="$ROOT/src"
python -m sdd_context.cli e2e
