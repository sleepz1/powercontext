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
