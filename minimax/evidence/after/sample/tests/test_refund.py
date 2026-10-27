"""New behavior required by specs/refund_eligibility.md."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refund import is_refund_eligible  # noqa: E402


def test_cancelled_never_refundable():
    assert is_refund_eligible(
        {"status": "CANCELLED", "age_days": 1, "amount": 50}
    ) is False


def test_day_seven_inclusive():
    assert is_refund_eligible(
        {"status": "PAID", "age_days": 7, "amount": 50}
    ) is True
