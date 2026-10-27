from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings, get_settings
from .context_pack import build_context_pack
from .db import SeekDB
from .minimax_client import MiniMaxClient
from .powerctx import PowerContextClient


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _run_pytest(sample_root: Path) -> subprocess.CompletedProcess[str]:
    env_python = Path(sys.executable)
    return subprocess.run(
        [str(env_python), "-m", "pytest", "-q", str(sample_root / "tests")],
        cwd=str(sample_root),
        capture_output=True,
        text=True,
    )


def import_sample(db: SeekDB, sample_root: Path, *, spec_version: str = "v1") -> None:
    spec_name = (
        "refund_eligibility.md" if spec_version == "v1" else "refund_eligibility_v2.md"
    )
    # For v2 we still key path as refund_eligibility.md but bump version so
    # latest_applicable_specs picks it up, demonstrating CHANGES after re-import.
    specs_dir = sample_root / "specs"
    if spec_version == "v1":
        content = (specs_dir / "refund_eligibility.md").read_text(encoding="utf-8")
        title = "Refund Eligibility v1"
    else:
        content = (specs_dir / "refund_eligibility_v2.md").read_text(encoding="utf-8")
        title = "Refund Eligibility v2"

    db.upsert_material(
        kind="spec",
        path="specs/refund_eligibility.md",
        title=title,
        content=content,
        version=spec_version,
        tags="refund,eligibility",
    )
    code = (sample_root / "src" / "refund.py").read_text(encoding="utf-8")
    db.upsert_material(
        kind="code",
        path="src/refund.py",
        title="refund.py",
        content=code,
        version="current",
        tags="target",
    )
    for test_file in sorted((sample_root / "tests").glob("test_*.py")):
        db.upsert_material(
            kind="test",
            path=f"tests/{test_file.name}",
            title=test_file.name,
            content=test_file.read_text(encoding="utf-8"),
            version="current",
            tags="pytest",
        )
    db.upsert_material(
        kind="task",
        path="task/ae02",
        title="AE-02 fix refund eligibility",
        content=(
            "Implement CANCELLED rejection and inclusive age_days<=7 per applicable specs. "
            "Keep regression tests green."
        ),
        version="v1",
        tags="active",
    )


def assemble_from_db(db: SeekDB) -> tuple[str, dict[str, Any]]:
    specs = db.latest_applicable_specs()
    code_rows = db.query_materials(kinds=["code"])
    test_rows = db.query_materials(kinds=["test"])
    task_notes = db.query_materials(kinds=["task"])
    pack = build_context_pack(
        specs=specs,
        code_rows=code_rows,
        test_rows=test_rows,
        task_notes=task_notes,
    )
    meta = {
        "spec_count": len(specs),
        "code_count": len(code_rows),
        "test_count": len(test_rows),
        "spec_versions": [f"{s['path']}@{s['version']}" for s in specs],
        "spec_titles": [s["title"] for s in specs],
        "digest_preview": pack[:200],
    }
    return pack, meta


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def snapshot_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


class Pipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.db = SeekDB(self.settings)
        self.pc = PowerContextClient(self.settings)
        self.mm = MiniMaxClient(self.settings)
        self.evidence = self.settings.evidence_root

    def init_all(self) -> dict[str, Any]:
        self.db.init_schema()
        self.db.reset_materials()
        health = self.pc.health()
        scope = self.pc.ensure_scope()
        return {"db": "ready", "powercontext": health, "scope_id": scope}

    def run_before_tests(self) -> dict[str, Any]:
        snap = self.evidence / "before" / "sample"
        snapshot_tree(self.settings.sample_root, snap)
        proc = _run_pytest(self.settings.sample_root)
        log = self.evidence / "logs" / "before_pytest.txt"
        write_text(
            log,
            f"command: {sys.executable} -m pytest -q tests\n"
            f"cwd: {self.settings.sample_root}\n"
            f"exit_code: {proc.returncode}\n"
            f"timestamp: {_now()}\n\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n",
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "log": str(log),
            "expect_fail": True,
            "ok_as_before": proc.returncode != 0,
        }

    def import_and_context(self, *, spec_version: str = "v1") -> dict[str, Any]:
        import_sample(self.db, self.settings.sample_root, spec_version=spec_version)
        pack, meta = assemble_from_db(self.db)
        out = self.evidence / "logs" / f"context_pack_{spec_version}.txt"
        write_text(out, pack)
        qlog = self.db.dump_query_log()
        write_text(
            self.evidence / "db" / "query_log.json",
            json.dumps(qlog, ensure_ascii=False, indent=2, default=str),
        )
        return {"pack_path": str(out), "meta": meta, "pack": pack}

    def call_minimax_and_apply(self, pack: str) -> dict[str, Any]:
        target = self.settings.sample_root / "src" / "refund.py"
        current = target.read_text(encoding="utf-8")
        result = self.mm.edit_code(
            context_pack=pack,
            target_path="src/refund.py",
            current_source=current,
        )
        record_path = self.mm.save_record(result, self.evidence / "minimax")
        # Apply
        write_text(target, result.extracted_code)
        # Update DB code material to reflect edit
        self.db.upsert_material(
            kind="code",
            path="src/refund.py",
            title="refund.py",
            content=result.extracted_code,
            version="current",
            tags="target,minimax-edited",
        )
        # Diff
        before_file = self.evidence / "before" / "sample" / "src" / "refund.py"
        diff_proc = subprocess.run(
            ["diff", "-u", str(before_file), str(target)],
            capture_output=True,
            text=True,
        )
        diff_path = self.evidence / "after" / "refund.py.diff"
        write_text(diff_path, diff_proc.stdout or diff_proc.stderr)
        write_text(self.evidence / "after" / "refund.py", result.extracted_code)
        return {
            "request_id": result.request_id,
            "model": result.model,
            "prompt_digest": result.prompt_digest,
            "record": str(record_path),
            "diff": str(diff_path),
            "code_len": len(result.extracted_code),
        }

    def run_after_tests(self) -> dict[str, Any]:
        snap = self.evidence / "after" / "sample"
        snapshot_tree(self.settings.sample_root, snap)
        proc = _run_pytest(self.settings.sample_root)
        log = self.evidence / "logs" / "after_pytest.txt"
        write_text(
            log,
            f"command: {sys.executable} -m pytest -q tests\n"
            f"cwd: {self.settings.sample_root}\n"
            f"exit_code: {proc.returncode}\n"
            f"timestamp: {_now()}\n"
            f"pytest_version: {subprocess.run([sys.executable,'-m','pytest','--version'], capture_output=True, text=True).stdout.strip()}\n\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n",
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "log": str(log),
            "ok": proc.returncode == 0,
        }

    def save_task_state(self, summary: dict[str, Any]) -> dict[str, Any]:
        text = (
            "AE-02 task state: refund eligibility fix via MiniMax. "
            f"request_id={summary.get('request_id')} "
            f"prompt_digest={summary.get('prompt_digest')} "
            f"after_tests_exit={summary.get('after_exit')} "
            f"spec_versions={summary.get('spec_versions')} "
            "next: reuse this state after module restart for context/prepare."
        )
        saved = self.pc.remember_task_state(text, reason="AE-02 progress checkpoint")
        self.pc.ingest_source(
            source_id=f"ae02-summary-{summary.get('request_id', 'x')}",
            content=json.dumps(summary, ensure_ascii=False, indent=2),
            metadata={"origin": "sdd_context_pipeline"},
        )
        write_text(
            self.evidence / "powercontext" / "remember.json",
            json.dumps(saved, ensure_ascii=False, indent=2, default=str),
        )
        write_text(
            self.evidence / "powercontext" / "scope_id.txt",
            self.pc.scope_id or "",
        )
        return saved

    def reuse_after_restart(self) -> dict[str, Any]:
        # Simulate module restart: new client, same scope key
        fresh = PowerContextClient(self.settings)
        scope = fresh.ensure_scope()
        prepared = fresh.prepare(query="refund eligibility MiniMax AE-02 task state", max_bytes=6000)
        write_text(
            self.evidence / "powercontext" / "prepare_after_restart.json",
            json.dumps(prepared, ensure_ascii=False, indent=2, default=str),
        )
        return {"scope_id": scope, "prepared": prepared}

    def demonstrate_spec_change(self) -> dict[str, Any]:
        before_pack, before_meta = assemble_from_db(self.db)
        import_sample(self.db, self.settings.sample_root, spec_version="v2")
        after_pack, after_meta = assemble_from_db(self.db)
        write_text(self.evidence / "logs" / "context_pack_after_spec_update.txt", after_pack)
        changed = before_pack != after_pack
        write_text(
            self.evidence / "logs" / "context_pack_change_summary.json",
            json.dumps(
                {
                    "changed": changed,
                    "before_titles": before_meta["spec_titles"],
                    "after_titles": after_meta["spec_titles"],
                    "before_versions": before_meta["spec_versions"],
                    "after_versions": after_meta["spec_versions"],
                },
                indent=2,
            ),
        )
        return {"changed": changed, "before_meta": before_meta, "after_meta": after_meta}
