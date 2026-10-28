from __future__ import annotations

from typing import Any


REQUIRED_SECTIONS = (
    "applicable_specs",
    "files_to_change",
    "tests_for_change",
    "compat_tests",
    "done_todo_prior",
)


def build_context_pack(
    *,
    specs: list[dict[str, Any]],
    code_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    task_notes: list[dict[str, Any]] | None = None,
    prior_verification: str = "",
) -> str:
    """Assemble a human-readable context pack from DB rows."""
    parts: list[str] = []
    parts.append("# SDD Context Pack")
    parts.append("")
    parts.append("## applicable_specs")
    if not specs:
        parts.append("(none)")
    for row in specs:
        parts.append(f"### {row['title']} [{row['path']} @ {row['version']}]")
        parts.append(row["content"].rstrip())
        parts.append("")

    parts.append("## files_to_change")
    for row in code_rows:
        parts.append(f"### {row['path']}")
        parts.append("```python")
        parts.append(row["content"].rstrip())
        parts.append("```")
        parts.append("")

    change_tests = [r for r in test_rows if "regression" not in r["path"]]
    compat_tests = [r for r in test_rows if "regression" in r["path"]]

    parts.append("## tests_for_change")
    for row in change_tests:
        parts.append(f"### {row['path']}")
        parts.append("```python")
        parts.append(row["content"].rstrip())
        parts.append("```")
        parts.append("")

    parts.append("## compat_tests")
    for row in compat_tests:
        parts.append(f"### {row['path']}")
        parts.append("```python")
        parts.append(row["content"].rstrip())
        parts.append("```")
        parts.append("")

    parts.append("## done_todo_prior")
    if task_notes:
        for row in task_notes:
            parts.append(f"- ({row.get('kind')}) {row.get('title')}: {row.get('content')[:500]}")
    else:
        parts.append("- todo: implement missing refund eligibility rules from applicable specs")
        parts.append("- done: sample project imported into seekdb")
    if prior_verification:
        parts.append(f"- prior_verification: {prior_verification}")
    else:
        parts.append("- prior_verification: none yet")

    text = "\n".join(parts) + "\n"
    # Ensure required section headers exist
    for section in REQUIRED_SECTIONS:
        if f"## {section}" not in text:
            raise RuntimeError(f"context pack missing section {section}")
    return text
