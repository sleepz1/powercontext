# MiniMax × OceanBase — AE-02 SDD Context Module

规有所依：面向软件持续演进的 SDD 上下文管理系统（第六届 OceanBase 大赛 AE-02）。

## What this is

A CLI module, validated on Linux cloud runners, that:

1. Imports specs / code / tests into **seekdb**
2. Assembles an SDD context pack from **SQL query results**
3. Calls **MiniMax** to edit the sample project
4. Runs fail→pass tests (new behavior + regressions)
5. Saves task state in **PowerContext** and reuses it after restart
6. Re-imports an updated spec and shows context **CHANGES**

## Quick start

See [RUNBOOK.md](./RUNBOOK.md). One-shot:

```bash
bash scripts/run_e2e.sh
```

## Layout

```
minimax/
  src/sdd_context/     # context module + CLI
  sample/billing_refund/
  evidence/            # before/after, diffs, logs, MiniMax/DB/PC records
  scripts/
  RUNBOOK.md VALIDATION.md ARCHITECTURE.md
```

## License notes

- This directory's original code: Apache-2.0 aligned with the parent `powercontext` competition ecosystem branch.
- PowerContext / seekdb / MiniMax are third-party services/SDKs; follow their respective licenses and terms. No vendor credentials are committed.

This independent backup is tracked in [draft PR 11](https://github.com/sleepz1/powercontext/pull/11). Real seekdb and PowerContext validation and historical-output RED/GREEN have passed in cloud; a fresh MiniMax repair requires the runtime Actions secret `MINIMAX_API_KEY`. See [SELF_CHECK.md](./SELF_CHECK.md) for exact evidence and the remaining live-validation dependency.
