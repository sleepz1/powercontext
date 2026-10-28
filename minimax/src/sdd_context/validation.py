"""Acceptance checks against artifacts produced by the current run."""
from pathlib import Path
from xml.etree import ElementTree as ET


def inspect_tests(exit_code: int, report: Path, *, expect_red: bool) -> dict:
    if not report.is_file():
        return {"ok": False, "reason": "missing JUnit report"}
    cases = ET.parse(report).findall(".//testcase")
    errors = [c.attrib.get("name") for c in cases if c.find("error") is not None]
    skipped = [c.attrib.get("name") for c in cases if c.find("skipped") is not None]
    failed = [c.attrib.get("name") for c in cases if c.find("failure") is not None]
    regressions = [c for c in cases if "regression" in c.attrib.get("classname", "")]
    targets = {"test_cancelled_never_refundable", "test_day_seven_inclusive"}
    regression_ok = bool(regressions) and all(len(c) == 0 for c in regressions)
    assertions = all("AssertionError" in (c.find("failure").attrib.get("message", "") + c.find("failure").attrib.get("type", "") + (c.find("failure").text or "")) for c in cases if c.find("failure") is not None)
    if expect_red:
        ok = exit_code == 1 and set(failed) == targets and assertions and regression_ok
    else:
        ok = exit_code == 0 and not failed and regression_ok and targets.issubset({c.attrib.get("name") for c in cases})
    return {"ok": bool(cases) and not errors and not skipped and ok, "cases": len(cases), "failures": failed, "errors": errors, "skipped": skipped, "regressions_pass": regression_ok}


def verify_edit(before: str, after: str, record: dict) -> bool:
    return bool(record.get("request_id")) and before != after and record.get("extracted_code") == after


def verify_query_log(rows: list[dict]) -> bool:
    positive = [r for r in rows if r.get("row_count", 0) > 0]
    return any(r.get("purpose") == "latest_specs" for r in positive) and all(
        any(r.get("purpose") == "assemble_context" and f'"{kind}"' in r.get("sql_text", "") for r in positive)
        for kind in ("code", "test", "task")
    )
