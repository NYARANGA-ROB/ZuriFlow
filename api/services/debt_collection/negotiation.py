"""Payment negotiation engine for debt collection."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from api.services.debt_collection.prompts import OFFER_MESSAGES
from api.services.debt_collection.types import (
    DebtAccount,
    DebtCollectionSession,
    NegotiationOffer,
    NegotiationOutcome,
)


def _message(locale: str, key: str, **kwargs: Any) -> str:
    bucket = OFFER_MESSAGES.get(key, {})
    template = bucket.get(locale) or bucket.get("mixed") or bucket.get("en", "")
    return template.format(**kwargs)


class PaymentNegotiationEngine:
    """Polite negotiation: offers, counters, and commitment extraction."""

    def __init__(
        self,
        *,
        min_upfront_pct: float = 0.15,
        max_term_months: int = 6,
        min_installment_kes: float = 500.0,
    ) -> None:
        self._min_upfront_pct = min_upfront_pct
        self._max_term_months = max_term_months
        self._min_installment_kes = min_installment_kes

    def open_negotiation(self, session: DebtCollectionSession) -> NegotiationOffer:
        if not session.account:
            raise ValueError("account_required")
        account = session.account
        offer = NegotiationOffer(
            offered_amount=account.outstanding_balance,
            term_months=1,
            upfront_amount=account.outstanding_balance,
            message_key="full_settlement",
            acceptable=True,
        )
        session.current_offer = offer
        session.negotiation_rounds += 1
        return offer

    def evaluate_customer_offer(
        self,
        session: DebtCollectionSession,
        amount: float,
    ) -> NegotiationOffer:
        if not session.account:
            raise ValueError("account_required")
        account = session.account
        session.negotiation_rounds += 1

        floor = account.settlement_floor
        min_today = round(account.outstanding_balance * self._min_upfront_pct, 2)

        if amount >= account.outstanding_balance:
            offer = NegotiationOffer(
                offered_amount=amount,
                term_months=1,
                upfront_amount=amount,
                message_key="full_settlement",
                acceptable=True,
            )
            session.outcome = NegotiationOutcome.FULL_PAYMENT
        elif amount >= floor:
            offer = NegotiationOffer(
                offered_amount=amount,
                term_months=1,
                upfront_amount=amount,
                message_key="full_settlement",
                acceptable=True,
            )
            session.outcome = NegotiationOutcome.PARTIAL_COMMITMENT
        elif amount >= min_today:
            remainder = round(account.outstanding_balance - amount, 2)
            months = min(
                self._max_term_months,
                max(2, int(remainder / self._min_installment_kes) + 1),
            )
            offer = NegotiationOffer(
                offered_amount=account.outstanding_balance,
                term_months=months,
                upfront_amount=amount,
                message_key="installment_offer",
                acceptable=True,
            )
            session.outcome = NegotiationOutcome.INSTALLMENT_PLAN
        else:
            offer = NegotiationOffer(
                offered_amount=min_today,
                term_months=1,
                upfront_amount=min_today,
                message_key="counter_offer",
                acceptable=False,
            )
            session.outcome = NegotiationOutcome.PENDING

        session.current_offer = offer
        return offer

    def format_offer_message(
        self,
        offer: NegotiationOffer,
        account: DebtAccount,
        locale: str = "mixed",
    ) -> str:
        loc = locale if locale in ("en", "sw", "mixed") else "mixed"
        if offer.message_key == "full_settlement":
            return _message(loc, "full_settlement", amount=f"{offer.offered_amount:,.0f}")
        if offer.message_key == "counter_offer":
            return _message(loc, "counter_offer", amount=f"{offer.upfront_amount:,.0f}")
        installment = round(
            (offer.offered_amount - offer.upfront_amount) / max(1, offer.term_months - 1)
            if offer.term_months > 1
            else offer.offered_amount,
            2,
        )
        return _message(
            loc,
            "installment_offer",
            amount=f"{offer.offered_amount:,.0f}",
            count=offer.term_months,
            installment=f"{installment:,.0f}",
        )

    def record_acceptance(self, session: DebtCollectionSession) -> NegotiationOutcome:
        if not session.current_offer:
            return session.outcome
        if session.outcome == NegotiationOutcome.PENDING:
            if session.current_offer.term_months > 1:
                session.outcome = NegotiationOutcome.INSTALLMENT_PLAN
            elif session.current_offer.upfront_amount >= (session.account.outstanding_balance if session.account else 0):
                session.outcome = NegotiationOutcome.FULL_PAYMENT
            else:
                session.outcome = NegotiationOutcome.PARTIAL_COMMITMENT
        return session.outcome


_negotiation: PaymentNegotiationEngine | None = None


def get_payment_negotiation_engine() -> PaymentNegotiationEngine:
    global _negotiation
    if _negotiation is None:
        _negotiation = PaymentNegotiationEngine()
    return _negotiation
