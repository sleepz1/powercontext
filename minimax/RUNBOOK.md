# AE-02 MiniMax SDD — Runbook

## Versions used for validation

| Component | Version / note |
|---|---|
| Python | 3.13 (3.11+ required) |
| pytest | 9.x |
| pymysql | 1.2.x |
| PowerContext | `powercontext 1.4.2.dev4+gcdb8da296` (install from oceanbase/powercontext@master) |
| seekdb | OceanBase seekdb-v1.4.0.0 (MySQL protocol, port 13881 in this environment) |
| MiniMax | `MiniMax-M2.5` via `https://api.minimaxi.com/v1` (OpenAI-compatible) |

## Prerequisites

1. **seekdb or OceanBase** reachable over MySQL protocol.
2. **PowerContext server** running locally.
3. **MiniMax Token Plan key** available via `MINIMAX_API_KEY` or `MINIMAX_KEY_FILE` (never commit the key).

## Configuration

```bash
cd minimax
cp .env.example .env
# edit SEEKDB_* / POWERCONTEXT_URL / MINIMAX_*
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

## Init data & services

```bash
# PowerContext (separate terminal)
uv tool install --force "powercontext[cli,server] @ git+https://github.com/oceanbase/powercontext.git@master"
powercontext server run   # default http://127.0.0.1:8000

# seekdb: start your local seekdb/OB and set SEEKDB_PORT accordingly
# Schema + scope:
PYTHONPATH=src python -m sdd_context.cli init
```

## Entry points

```bash
export PYTHONPATH=src
python -m sdd_context.cli init
python -m sdd_context.cli before-test      # expect FAIL (missing behavior)
python -m sdd_context.cli context          # DB → context pack
python -m sdd_context.cli fix              # MiniMax edits sample/src/refund.py
python -m sdd_context.cli after-test       # expect PASS
python -m sdd_context.cli save-state
python -m sdd_context.cli reuse-state      # new client, same scope key
python -m sdd_context.cli spec-update      # re-import v2 → context CHANGES
# Or one shot:
python -m sdd_context.cli e2e
```

Convenience: `./scripts/run_e2e.sh` and `./scripts/reset.sh`.

## Test commands (sample project)

```bash
cd sample/billing_refund
pytest -q
```

## Limits / notes

- Docker is optional; this runbook uses a local seekdb binary/MySQL port.
- MiniMax key must stay outside git (`.env` is gitignored; only `.env.example` is committed).
- `e2e` restores evidence under `evidence/`; `reset.sh` restores the buggy `refund.py` from `evidence/before` if present, else from git.
- Platform judges need a clean clone: start seekdb + PowerContext, set env, run `e2e`.
