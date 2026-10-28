# AE-02 MiniMax SDD — Runbook

Use a Linux cloud runner. The delivered GitHub workflow `.github/workflows/ae02-backup.yml` provisions real services and retains evidence; no contest code was executed on the Windows editing machine.

## Reproduce on GitHub Actions

1. Use `contest/ae02-minimax-backup` in `sleepz1/powercontext`; the original `contest/ae02-minimax` remains untouched.
2. Push this branch to trigger **AE-02 backup validation**. Pull requests run the credential-free contracts job only.
3. For a fresh MiniMax repair, configure repository Actions secret `MINIMAX_API_KEY` using the authorized MiniMax Token Plan key. The workflow injects it only into the acceptance step on the trusted backup branch. Never place it in source, workflow text, arguments or logs.
4. Re-run the services job after provisioning the secret, or push another reviewed commit. Inspect the report and artifact attached to that exact commit.

Without the secret the services job still runs real seekdb imports/queries, behavioral baseline tests, PowerContext empty→save→separate-process resume→context use, and v2 specification reimport. Its report says `live-validation-blocked-no-key`, with criteria 2 and 6 false. A green services job in this mode is not a complete live acceptance pass.

The contracts job also executes the original sample against the delivered historical MiniMax output: two target assertions fail before and all five tests pass after. This checks the historical artifact, not a new API call.

## Versions and configuration

| Component | Reproduction version |
|---|---|
| Runner | Ubuntu 24.04, Python 3.11 |
| Pipeline dependencies | `requirements.txt`; exact installed versions in artifact `logs/dependencies.txt` |
| PowerContext | `cdb8da296a8ed1ad06ac851af7fd05139907a966` (`1.4.2.dev4`) |
| seekdb | `oceanbase/seekdb@sha256:4db4961869d554313520d6081fca29265ba6da6db7313311bd8acbed771a956b` (`1.4.0.0`) |
| MiniMax | `MiniMax-M2.5`, `https://api.minimaxi.com/v1/chat/completions` |

The pipeline uses seekdb through PyMySQL and PowerContext through HTTP. PowerContext stores explicit memory in its persistent SQLite backend; seekdb stores and queries engineering materials. No additional inference API is required by PowerContext.

For an independent Linux cloud VM, start the pinned seekdb container, expose port 2881 as 13881 on loopback, and install/start the pinned PowerContext server:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install 'powercontext[cli,server] @ git+https://github.com/oceanbase/powercontext.git@cdb8da296a8ed1ad06ac851af7fd05139907a966'
export POWERCONTEXT_HOME="$PWD/.powercontext-data"
powercontext server run --no-env-file
```

In a second cloud terminal, set `.env` from `.env.example` or export configuration. Prefer runtime `MINIMAX_API_KEY`; a protected external `MINIMAX_KEY_FILE` is also supported. Then, from `minimax/`:

```bash
bash scripts/run_e2e.sh
```

That script installs dependencies in `.venv`, restores the committed buggy baseline and runs the full CLI pipeline. `e2e` initializes/clears the configured dedicated `ae02_minimax` database and creates a unique empty PowerContext scope. Use a dedicated database, as documented in `.env.example`.

## CLI inputs and outputs

```bash
export PYTHONPATH="$PWD/src"
python -m sdd_context.cli init          # DB schema/reset + scope; no model key needed
python -m sdd_context.cli before-test   # exits 0 only for the two intended assertion failures
python -m sdd_context.cli context       # imports files; SQL → context_pack_v1.txt
python -m sdd_context.cli fix           # live MiniMax → only src/refund.py + record/diff
python -m sdd_context.cli after-test    # all five tests, no errors/skips
python -m sdd_context.cli save-state    # remember + source checkpoint
python -m sdd_context.cli reuse-state   # separate interpreter; reuse in subsequent context
python -m sdd_context.cli spec-update   # v2 import → selected v2 context
```

`bash scripts/reset.sh` restores `sample/billing_refund/baseline/refund.py` without needing a virtualenv, model credential, mutable evidence or a running database. It leaves evidence intact. `e2e` and `init` initialize database data separately.

Reports, JUnit XML, before/after snapshots, source hashes, unchanged-test hashes, model request/final-answer records, SQL logs and PowerContext records are written to `EVIDENCE_ROOT` (default `minimax/evidence`). Cloud runs place this outside the checkout. The current report is written even on failure. Model records omit Authorization headers and private reasoning.

## Verified evidence and remaining dependency

Cloud run [40686517364](https://github.com/sleepz1/powercontext/actions/runs/40686517364) executed commit `eca8599be6113a5df08b71b0a3fc9463675b8845`: six contracts passed and real services passed in `services-only` mode. The preserved report is `evidence/cloud/eca8599/logs/e2e_report.json`. Its fresh MiniMax call and live repair remain blocked until `MINIMAX_API_KEY` is provisioned. Historical evidence under the original `evidence/` paths is retained as historical, not evidence that the new backup performed a live model call.
