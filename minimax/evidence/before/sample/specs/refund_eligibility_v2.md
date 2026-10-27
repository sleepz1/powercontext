# Spec: Refund Eligibility (v2 — updated)

## Goal
Decide whether a completed order may receive a refund.

## Rules
1. Orders with `status == "CANCELLED"` are **never** refundable.
2. An order is refundable only when `age_days <= 7` (day 7 is **inclusive**).
3. An order with `amount <= 0` is never refundable.
4. Status comparison is case-sensitive against uppercase enum values: `PAID`, `CANCELLED`, `REFUNDED`.
5. **NEW in v2:** Orders with `status == "REFUNDED"` are never refundable again.

## Change log
- v2: add REFUNDED guard so double-refund attempts are rejected.
