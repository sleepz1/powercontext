# MiniMax × OceanBase — AE-02 SDD Context Module

规有所依：面向软件持续演进的 SDD 上下文管理系统（第六届 OceanBase 大赛 AE-02）。

## What this is

A local CLI module that:

1. Imports specs / code / tests into **seekdb**
2. Assembles an SDD context pack from **SQL query results**
3. Calls **MiniMax** to edit the sample project
4. Runs fail→pass tests (new behavior + regressions)
5. Saves task state in **PowerContext** and reuses it after restart
6. Re-imports an updated spec and shows context **CHANGES**

## Quick start

See [RUNBOOK.md](./RUNBOOK.md). One-shot:

```bash
./scripts/run_e2e.sh
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
