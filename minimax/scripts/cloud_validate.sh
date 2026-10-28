#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true ]] || { echo 'Run this harness on GitHub Actions.'; exit 2; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/src"
mkdir -p "$EVIDENCE_ROOT/logs" "$POWERCONTEXT_HOME"
python -m pip freeze > "$EVIDENCE_ROOT/logs/dependencies.txt"
trap 'kill "${PC_PID:-}" 2>/dev/null || true; docker logs ae02-seekdb > "$EVIDENCE_ROOT/logs/seekdb.log" 2>&1 || true; docker rm -f ae02-seekdb >/dev/null 2>&1 || true' EXIT
docker run -d --name ae02-seekdb -p 127.0.0.1:13881:2881 \
  oceanbase/seekdb@sha256:4db4961869d554313520d6081fca29265ba6da6db7313311bd8acbed771a956b
powercontext server run --no-env-file > "$EVIDENCE_ROOT/logs/powercontext-server.log" 2>&1 &
PC_PID=$!
python "$ROOT/scripts/wait_services.py"
bash "$ROOT/scripts/reset.sh"
if [[ -n "${MINIMAX_API_KEY:-}" ]]; then
  python -m sdd_context.e2e
else
  python -m sdd_context.e2e --services-only
  echo '::warning::MINIMAX_API_KEY is absent. Real database and state validation ran; live MiniMax repair and GREEN remain unverified.'
fi
python - "$EVIDENCE_ROOT/logs/e2e_report.json" <<'PY'
import json, os, sys
report = json.load(open(sys.argv[1]))
summary = f"AE-02: {report['status']}\n\nMode: {report['mode']}\n\nCriteria: {report['criteria']}\n"
print(summary)
with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
    out.write(summary)
PY
