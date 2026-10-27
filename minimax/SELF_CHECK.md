# Self-check against AE-02 mandatory items (local evidence)

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Runnable from clean env via runbook | PASS (local) | `RUNBOOK.md`, `scripts/run_e2e.sh`, `evidence/logs/e2e_report.json` |
| 2 | MiniMax call matches code diff | PASS | `evidence/minimax/minimax_072fbf3694cd03236639095d808a9b3a.json` extracted_code == `evidence/after/refund.py`; diff `evidence/after/refund.py.diff` |
| 3 | Context pack sources + CHANGES after re-import | PASS | `evidence/logs/context_pack_v1.txt` (specs/code/tests/done_todo); `context_pack_change_summary.json` changed=true (v1→v2) |
| 4 | DB queries build context | PASS | `evidence/db/query_log.json` (latest_specs / assemble_context, row_count>0) |
| 5 | Task state empty→save→restart→reuse | PASS | `evidence/powercontext/remember.json` + `prepare_after_restart.json` status=ready, non-empty content |
| 6 | Fail before / pass after; regressions green | PASS | `evidence/logs/before_pytest.txt` exit=1 (2 failed missing behavior); `after_pytest.txt` exit=0 (5 passed) |

**Not a platform score.** Official score is assigned only after TestRecord submit.

Committed `sample/.../refund.py` is the **buggy** baseline; `./scripts/run_e2e.sh` re-runs MiniMax and regenerates evidence.
