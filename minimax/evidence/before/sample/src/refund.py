"""Refund eligibility helper (intentionally incomplete for AE-02 demo)."""

from __future__ import annotations

from typing import Mapping, Any


def is_refund_eligible(order: Mapping[str, Any]) -> bool:
    """Return True when the order may be refunded.

    Current implementation is incomplete relative to
    specs/refund_eligibility.md (missing CANCELLED guard;
    exclusive age bound).
    """
    amount = order.get("amount", 0)
    if amount is None or amount <= 0:
        return False

    age_days = order.get("age_days", 0)
    if age_days is None:
        return False

    # BUG: exclusive upper bound; day 7 should still be eligible.
    if age_days >= 7:
        return False

    # BUG: CANCELLED orders are not rejected here.
    return True
