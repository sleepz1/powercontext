"""Refund eligibility helper."""

from __future__ import annotations

from typing import Mapping, Any


def is_refund_eligible(order: Mapping[str, Any]) -> bool:
    """Return True when the order may be refunded."""
    if order.get("status") != "PAID":
        return False

    amount = order.get("amount", 0)
    if amount is None or amount <= 0:
        return False

    age_days = order.get("age_days", 0)
    if age_days is None or age_days > 7:
        return False

    return True
