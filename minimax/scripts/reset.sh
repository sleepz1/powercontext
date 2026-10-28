#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cp "$ROOT/sample/billing_refund/baseline/refund.py" "$ROOT/sample/billing_refund/src/refund.py"
echo 'Restored the committed buggy baseline; init/e2e initializes database data.'
