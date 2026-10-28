#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install -r requirements.txt
bash "$ROOT/scripts/reset.sh"
export PYTHONPATH="$ROOT/src"
python -m sdd_context.cli e2e
