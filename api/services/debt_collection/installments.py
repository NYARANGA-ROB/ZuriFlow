"""Installment scheduling for debt collection."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Literal

from api.services.debt_collection.types import (
    CommitmentStatus,
    DebtAccount,
    InstallmentPlan,
    NegotiationOffer,
    PaymentCommitment,
)

Frequency = Literal["weekly", "biweekly", "monthly"]


class InstallmentScheduler:
    """Build and validate installment schedules."""

    def __init__(
        self,
        *,
        max_term_months: int = 6,
        min_installment_kes: float = 500.0,
    ) -> None:
        self._max_term_months = max_term_months
        self._min_installment_kes = min_installment_kes

    def _next_date(self, start: date, index: int, frequency: Frequency) -> date:
        if frequency == "weekly":
            return start + timedelta(weeks=index)
        if frequency == "biweekly":
            return start + timedelta(weeks=index * 2)
        return start + timedelta(days=30 * index)

    def build_plan(
        self,
        account: DebtAccount,
        offer: NegotiationOffer,
        *,
        frequency: Frequency = "monthly",
        start_date: date | None = None,
    ) -> InstallmentPlan:
        start = start_date or date.today()
        total = account.outstanding_balance
        upfront = round(offer.upfront_amount, 2)
        remaining = round(total - upfront, 2)
        term = min(offer.term_months, self._max_term_months)
        if term < 1:
            term = 1

        commitments: list[PaymentCommitment] = []
        idx = 0

        if upfront > 0:
            commitments.append(
                PaymentCommitment(
                    commitment_id=str(uuid.uuid4()),
                    amount=upfront,
                    due_date=start,
                    status=CommitmentStatus.PROPOSED,
                    installment_index=idx,
                    notes="upfront",
                )
            )
            idx += 1

        if remaining > 0 and term > 1:
            per = round(remaining / (term - 1), 2)
            if per < self._min_installment_kes:
                per = self._min_installment_kes
            scheduled = 0.0
            for i in range(term - 1):
                amt = per if i < term - 2 else round(remaining - scheduled, 2)
                scheduled += amt
                commitments.append(
                    PaymentCommitment(
                        commitment_id=str(uuid.uuid4()),
                        amount=amt,
                        due_date=self._next_date(start, i + 1, frequency),
                        status=CommitmentStatus.PROPOSED,
                        installment_index=idx,
                    )
                )
                idx += 1
        elif remaining > 0:
            commitments.append(
                PaymentCommitment(
                    commitment_id=str(uuid.uuid4()),
                    amount=remaining,
                    due_date=self._next_date(start, 1, frequency),
                    status=CommitmentStatus.PROPOSED,
                    installment_index=idx,
                )
            )

        return InstallmentPlan(
            plan_id=str(uuid.uuid4()),
            total_amount=total,
            installments=tuple(commitments),
            frequency=frequency,
            approved=False,
        )

    def approve_plan(self, plan: InstallmentPlan) -> InstallmentPlan:
        approved = tuple(
            PaymentCommitment(
                commitment_id=c.commitment_id,
                amount=c.amount,
                due_date=c.due_date,
                status=CommitmentStatus.ACCEPTED,
                installment_index=c.installment_index,
                notes=c.notes,
            )
            for c in plan.installments
        )
        from dataclasses import replace

        return replace(plan, installments=approved, approved=True)

    def summarize_whatsapp(self, plan: InstallmentPlan, locale: str = "mixed") -> str:
        lines = []
        if locale == "sw":
            lines.append("Mpango wako wa malipo:")
        else:
            lines.append("Your payment plan:")
        for c in plan.installments:
            lines.append(f"- KES {c.amount:,.0f} by {c.due_date.isoformat()}")
        lines.append(f"Total: KES {plan.total_amount:,.0f}")
        return "\n".join(lines)


_scheduler: InstallmentScheduler | None = None


def get_installment_scheduler() -> InstallmentScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = InstallmentScheduler()
    return _scheduler
