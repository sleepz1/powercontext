"""Current-run acceptance evidence, including failures and blocked live calls."""
import hashlib
import json
import os
from dataclasses import replace
from uuid import uuid4

from .config import get_settings
from .runner import Pipeline, write_text
from .validation import verify_query_log


def run(*, services_only=False):
    settings = get_settings()
    settings = replace(settings, powercontext_scope_key=f"{settings.powercontext_scope_key}-{uuid4().hex}")
    pipe = Pipeline(settings)
    report = {"commit": os.getenv("GITHUB_SHA", "unrecorded"), "scope_key": settings.powercontext_scope_key, "mode": "services-only" if services_only else "live", "steps": [], "criteria": {str(i): False for i in range(1, 7)}}
    def step(name, fn):
        result = fn()
        report["steps"].append({"name": name, "result": result})
        return result
    def require(condition, message):
        if not condition:
            raise RuntimeError(message)
    try:
        step("init", pipe.init_all)
        initial = pipe.pc.prepare("refund eligibility MiniMax AE-02 task state")
        write_text(pipe.evidence / "powercontext/prepare_empty.json", json.dumps(initial, indent=2))
        require(not initial.get("content"), "Fresh scope already contains state")
        baseline_tests = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (settings.sample_root / "tests").glob("test_*.py")}
        before = step("before-test", pipe.run_before_tests)
        require(before["ok_as_before"], "Baseline must fail only for the two specified assertions with all regressions passing")
        ctx = pipe.import_and_context()
        step("import+context", lambda: {k: v for k, v in ctx.items() if k != "pack"})
        qlog = pipe.db.dump_query_log()
        report["criteria"]["4"] = verify_query_log(qlog)
        require(report["criteria"]["4"], "SQL evidence lacks required material query results")
        fix = {"request_id": "services-only-no-model-call", "after_exit": None, "spec_versions": ctx["meta"]["spec_versions"]}
        if not services_only:
            fix = step("minimax-fix", lambda: pipe.call_minimax_and_apply(ctx["pack"]))
            require(fix["matches_applied_file"], "Model output does not match an actual source change")
            report["criteria"]["2"] = True
            after = step("after-test", pipe.run_after_tests)
            require(after["ok"], "Modified sample tests failed")
            current_tests = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (settings.sample_root / "tests").glob("test_*.py")}
            require(baseline_tests == current_tests, "Target or regression tests changed during repair")
            fix.update(after_exit=after["exit_code"], spec_versions=ctx["meta"]["spec_versions"])
            report["criteria"]["6"] = True
        fix["verification_mode"] = report["mode"]
        step("save-state", lambda: pipe.save_task_state(fix))
        restored = step("reuse-state", pipe.reuse_after_restart)
        require(restored["child_pid"] != restored["parent_pid"] and restored["used_in_context"], "Saved state was not used after interpreter restart")
        require(fix["request_id"] in restored["prepared"].get("content", ""), "Recovered memory is not this run's task")
        report["criteria"]["5"] = True
        changed = step("spec-update", pipe.demonstrate_spec_change)
        require(changed["changed"] and changed["after_meta"]["spec_versions"] == ["specs/refund_eligibility.md@v2"], "Spec reimport did not select v2")
        report["criteria"]["3"] = True
        report["criteria"]["1"] = True
        report["tests_sha256"] = baseline_tests
        report["status"] = "live-validation-blocked-no-key" if services_only else "passed"
        return 0
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        write_text(pipe.evidence / "logs/e2e_report.json", json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(run(services_only="--services-only" in __import__("sys").argv))
