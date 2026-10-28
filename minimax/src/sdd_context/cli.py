from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python -m sdd_context.cli` from src/
SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sdd_context.runner import Pipeline  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdd-context",
        description="AE-02 MiniMax SDD context module CLI",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Init seekdb schema + PowerContext scope")
    sub.add_parser("import-sample", help="Import sample specs/code/tests into seekdb")
    p_ctx = sub.add_parser("context", help="Assemble context pack from DB queries")
    p_ctx.add_argument("--spec-version", default="v1")
    sub.add_parser("before-test", help="Run tests on buggy sample (expect fail)")
    sub.add_parser("fix", help="Call MiniMax with context and apply code edit")
    sub.add_parser("after-test", help="Run tests after MiniMax edit (expect pass)")
    sub.add_parser("save-state", help="Persist task state into PowerContext")
    sub.add_parser("reuse-state", help="New client: prepare context after restart")
    sub.add_parser("spec-update", help="Re-import v2 spec and show context CHANGES")
    sub.add_parser("e2e", help="Run full validation pipeline")

    args = parser.parse_args(argv)
    pipe = Pipeline()

    if args.cmd == "init":
        print(json.dumps(pipe.init_all(), indent=2, default=str))
        return 0

    if args.cmd == "import-sample":
        pipe.db.init_schema()
        from sdd_context.runner import import_sample

        import_sample(pipe.db, pipe.settings.sample_root, spec_version="v1")
        print("imported sample v1")
        return 0

    if args.cmd == "context":
        pipe.db.init_schema()
        out = pipe.import_and_context(spec_version=args.spec_version)
        print(json.dumps({"pack_path": out["pack_path"], "meta": out["meta"]}, indent=2))
        return 0

    if args.cmd == "before-test":
        out = pipe.run_before_tests()
        print(json.dumps({k: out[k] for k in ("exit_code", "ok_as_before", "log")}, indent=2))
        print(out["stdout"])
        return 0 if out["ok_as_before"] else 1

    if args.cmd == "fix":
        # Never treat inherited or stale evidence as this invocation's SQL result.
        pipe.db.init_schema()
        pack = pipe.import_and_context(spec_version="v1")["pack"]
        result = pipe.call_minimax_and_apply(pack)
        print(json.dumps(result, indent=2))
        # stash for save-state
        (pipe.evidence / "logs" / "last_fix.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        return 0

    if args.cmd == "after-test":
        out = pipe.run_after_tests()
        print(json.dumps({k: out[k] for k in ("exit_code", "ok", "log")}, indent=2))
        print(out["stdout"])
        return 0 if out["ok"] else 1

    if args.cmd == "save-state":
        fix = {}
        p = pipe.evidence / "logs" / "last_fix.json"
        if p.exists():
            fix = json.loads(p.read_text(encoding="utf-8"))
        after_log = pipe.evidence / "logs" / "after_pytest.txt"
        after_exit = None
        if after_log.exists():
            for line in after_log.read_text(encoding="utf-8").splitlines():
                if line.startswith("exit_code:"):
                    after_exit = int(line.split(":", 1)[1].strip())
        summary = {
            **fix,
            "after_exit": after_exit,
            "spec_versions": ["specs/refund_eligibility.md@v1"],
        }
        saved = pipe.save_task_state(summary)
        print(json.dumps(saved, indent=2, default=str))
        return 0

    if args.cmd == "reuse-state":
        out = pipe.reuse_after_restart()
        prepared = out["prepared"]
        status = prepared.get("status")
        content = prepared.get("content") or ""
        print(
            json.dumps(
                {
                    "scope_id": out["scope_id"],
                    "status": status,
                    "content_preview": content[:500],
                    "used": bool(content),
                },
                indent=2,
            )
        )
        return 0 if content else 1

    if args.cmd == "spec-update":
        out = pipe.demonstrate_spec_change()
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["changed"] else 1

    if args.cmd == "e2e":
        from sdd_context.e2e import run
        return run()
    parser.error(f"unknown cmd {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
