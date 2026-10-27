# Validation sample

## Task

Fix `sample/billing_refund/src/refund.py` so refund eligibility matches `specs/refund_eligibility.md`:

1. `CANCELLED` orders are never refundable.
2. `age_days <= 7` is inclusive (day 7 allowed).
3. Keep amount and older-than-7 regressions green.

## Valid specifications

- `sample/billing_refund/specs/refund_eligibility.md` (v1, imported as version `v1`)
- Updated variant for CHANGE demo: `refund_eligibility_v2.md` (imported as version `v2` on same path)

## Seed data

- seekdb database `ae02_minimax`, tables `materials`, `query_log`
- Seeded by `python -m sdd_context.cli init` then `context` / `e2e`
- PowerContext scope idempotency key: `ae02-minimax-sdd` (configurable)

## Steps

1. Ensure seekdb + `powercontext server run` are up; configure `.env`.
2. `PYTHONPATH=src python -m sdd_context.cli e2e`
3. Inspect evidence paths listed below.

## Expected result

| Check | Expected |
|---|---|
| before-test | pytest exit ≠ 0 (new behavior missing; not env error) |
| MiniMax record | `evidence/minimax/minimax_<id>.json` extracted_code matches applied file / diff |
| context pack | contains specs, `src/refund.py`, `test_refund.py`, `test_regression.py`, done/todo |
| after spec-update | `evidence/logs/context_pack_change_summary.json` → `"changed": true` |
| DB | `evidence/db/query_log.json` shows SELECT queries with row_count > 0 |
| PowerContext | `remember.json` then `prepare_after_restart.json` with non-empty content |
| after-test | pytest exit 0; new + regression tests pass |

## Reset

```bash
./scripts/reset.sh
# restores buggy refund.py, clears evidence runtime artifacts optional,
# DELETE FROM materials via cli init
```
