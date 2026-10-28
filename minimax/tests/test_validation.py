from pathlib import Path

import pytest

from sdd_context.validation import inspect_tests, verify_edit, verify_query_log


def xml_report(tmp_path, body):
    path = tmp_path / "pytest.xml"
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>")
    return path


def test_red_rejects_environment_and_collection_errors(tmp_path):
    path = xml_report(tmp_path, '<testcase name="test_cancelled"><error>ImportError</error></testcase>')
    assert not inspect_tests(2, path, expect_red=True)["ok"]


def test_red_requires_target_assertions_and_passing_regressions(tmp_path):
    path = xml_report(tmp_path, '<testcase classname="tests.test_refund" name="test_cancelled_never_refundable"><failure type="AssertionError">assert True is False</failure></testcase><testcase classname="tests.test_refund" name="test_day_seven_inclusive"><failure type="AssertionError">assert False is True</failure></testcase><testcase classname="tests.test_regression" name="test_amount"/>')
    assert inspect_tests(1, path, expect_red=True)["ok"]
    path.write_text(path.read_text().replace('name="test_amount"/>', 'name="test_amount"><failure>bad</failure></testcase>'))
    assert not inspect_tests(1, path, expect_red=True)["ok"]


def test_green_rejects_skips_and_empty_suites(tmp_path):
    assert not inspect_tests(0, xml_report(tmp_path, ""), expect_red=False)["ok"]
    assert not inspect_tests(0, xml_report(tmp_path, '<testcase name="x"><skipped/></testcase>'), expect_red=False)["ok"]


def test_edit_must_match_model_record_and_change_source():
    assert verify_edit("old", "new", {"request_id": "real", "extracted_code": "new"})
    assert not verify_edit("old", "new", {"request_id": "real", "extracted_code": "different"})
    assert not verify_edit("same", "same", {"request_id": "real", "extracted_code": "same"})


def test_db_criteria_requires_all_material_queries():
    assert not verify_query_log([{"purpose": "latest_specs", "row_count": 1}])
    rows = [{"purpose": "latest_specs", "row_count": 1}]
    for kind in ("code", "test", "task"):
        rows.append({"purpose": "assemble_context", "sql_text": f'SELECT ... params=["{kind}"]', "row_count": 1})
    assert verify_query_log(rows)


def test_historical_model_output_has_real_sample_red_green(tmp_path):
    """Fresh executions of the delivered fixture, without claiming a new API call."""
    import json
    import shutil
    from sdd_context.config import Settings
    from sdd_context.runner import Pipeline

    root = Path(__file__).resolve().parents[1]
    sample = tmp_path / "sample"
    shutil.copytree(root / "sample/billing_refund", sample)
    shutil.copyfile(sample / "baseline/refund.py", sample / "src/refund.py")
    pipe = Pipeline(Settings(sample_root=sample, evidence_root=tmp_path / "evidence"))
    assert pipe.run_before_tests()["ok_as_before"]
    record = json.loads((root / "evidence/minimax/minimax_072fbf3694cd03236639095d808a9b3a.json").read_text())
    (sample / "src/refund.py").write_text(record["extracted_code"])
    assert pipe.run_after_tests()["ok"]


def test_model_record_preserves_actual_request_without_key_or_reasoning(monkeypatch, tmp_path):
    import json
    from sdd_context.config import Settings
    from sdd_context.minimax_client import MiniMaxClient

    monkeypatch.setenv("MINIMAX_API_KEY", "unit-test-placeholder")
    captured = {}
    class Response:
        status_code = 200
        def json(self):
            return {"id": "test-request", "model": "MiniMax-M2.5", "choices": [{"message": {"content": "<think>private reasoning</think>```python:src/refund.py\nanswer = 1\n```"}}]}
    def post(url, **kwargs):
        captured.update(kwargs)
        return Response()
    monkeypatch.setattr("sdd_context.minimax_client.requests.post", post)
    client = MiniMaxClient(Settings())
    result = client.edit_code(context_pack="database context", target_path="src/refund.py", current_source="answer = 0\n")
    path = client.save_record(result, tmp_path)
    serialized = path.read_text()
    saved = json.loads(serialized)
    assert saved["request_payload"] == captured["json"]
    assert "database context" in saved["request_payload"]["messages"][1]["content"]
    assert "unit-test-placeholder" not in serialized
    assert "private reasoning" not in serialized
