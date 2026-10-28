# AE-02 Architecture (one page)

```
┌─────────────┐   import specs/code/tests    ┌──────────────┐
│ sample/     │ ───────────────────────────► │ seekdb       │
│ billing_    │                              │ materials +  │
│ refund      │ ◄── SQL assemble context ─── │ query_log    │
└──────┬──────┘                              └──────────────┘
       │ apply MiniMax patch                        │
       ▼                                            ▼
┌─────────────┐   context pack + source      ┌──────────────┐
│ MiniMax API │ ◄────────────────────────────│ sdd_context  │
│ M2.5 chat   │ ── fixed refund.py ─────────►│ CLI pipeline │
└─────────────┘                              └──────┬───────┘
                                                    │
                     remember / prepare             ▼
                                             ┌──────────────┐
                                             │ PowerContext │
                                             │ scope+memory │
                                             └──────────────┘
```

## Division of labor

| Tech | Role in this module |
|---|---|
| **seekdb** | Stores engineering materials (`spec` / `code` / `test` / `task`). Context packs are built **only** from query results (`latest_applicable_specs`, `query_materials`). Query text + row counts land in `query_log` and `evidence/db/`. |
| **MiniMax** | Sole code editor for the sample fix. Prompt includes the DB-assembled pack; response is extracted and written to `sample/.../refund.py`. Request id + prompt digest + extracted code are stored under `evidence/minimax/` and must match `evidence/after/refund.py.diff`. |
| **PowerContext** | Persists task progress (`/v1/memory/remember`, `/v1/sources/content`). A separate Python interpreter reopens the same idempotent scope and calls `/v1/context/prepare`. Recovered state is inserted into `done_todo_prior` in a subsequent SQL-derived context pack. |

## Context selection

1. Import files into `materials` with kinds and versions.
2. `latest_applicable_specs` = max(version) per spec path (so re-importing v2 changes the pack).
3. Pack sections: `applicable_specs`, `files_to_change`, `tests_for_change`, `compat_tests`, `done_todo_prior`.
4. No hardcoded final answer in the pack — content comes from DB rows.

## Sample change

Buggy `is_refund_eligible` misses CANCELLED rejection and uses exclusive day-7 bound. Spec + new tests define the missing behavior; regression tests protect amount/age baselines.

The full E2E path creates a unique empty scope per run and writes current evidence outside the checkout on cloud. JUnit checks require exactly the two target assertion failures before repair, passing regressions, and no errors/skips; afterward the same unchanged tests must all pass. The MiniMax record retains the actual request body and final answer, and its extracted code must exactly match the applied file. No model key is needed to initialize the pipeline or resume state.
