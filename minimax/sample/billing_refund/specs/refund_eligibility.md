# Spec: Refund Eligibility (v1)

## Goal
Decide whether a completed order may receive a refund.

## Rules
1. Orders with `status == "CANCELLED"` are **never** refundable.
2. An order is refundable only when `age_days <= 7` (day 7 is **inclusive**).
3. An order with `amount <= 0` is never refundable.
4. Status comparison is case-sensitive against uppercase enum values: `PAID`, `CANCELLED`, `REFUNDED`.

## Non-goals
- Currency conversion
- Partial refunds
- Timezone conversion (callers pass integer `age_days`)

## Acceptance tests
- CANCELLED + age_days=1 → False
- PAID + age_days=7 → True
- PAID + age_days=8 → False
- PAID + age_days=0 + amount=10 → True
- PAID + amount=0 → False
