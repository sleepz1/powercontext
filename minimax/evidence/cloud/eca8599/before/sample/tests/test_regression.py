"""Regression coverage that must stay green after the fix."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refund import is_refund_eligible  # noqa: E402


def test_fresh_paid_order_refundable():
    assert is_refund_eligible(
        {"status": "PAID", "age_days": 0, "amount": 10}
    ) is True


def test_too_old_not_refundable():
    assert is_refund_eligible(
        {"status": "PAID", "age_days": 8, "amount": 10}
    ) is False


def test_zero_amount_not_refundable():
    assert is_refund_eligible(
        {"status": "PAID", "age_days": 1, "amount": 0}
    ) is False
