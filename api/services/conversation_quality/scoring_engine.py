"""Multi-dimension scoring engine for conversation quality."""

from __future__ import annotations

from typing import Any

from api.services.conversation_quality.types import (
    DEFAULT_DIMENSION_WEIGHTS,
    DimensionScore,
    QualityDimension,
)


class ConversationQualityScoringEngine:
    """Deterministic scorers for each evaluation dimension (0–100)."""

    def score_all(self, context: dict[str, Any]) -> list[DimensionScore]:
        return [
            self.score_response_quality(context),
            self.score_interruption_handling(context),
            self.score_payment_negotiation(context),
            self.score_latency(context),
            self.score_naturalness(context),
            self.score_escalation_correctness(context),
        ]

    def overall_score(self, dimensions: list[DimensionScore]) -> float:
        total_weight = sum(d.weight for d in dimensions) or 1.0
        return sum(d.score * d.weight for d in dimensions) / total_weight

    def score_response_quality(self, ctx: dict[str, Any]) -> DimensionScore:
        score = 75.0
        flags: list[str] = []
        tag_names = {t.get("tag", "") for t in ctx.get("qa_tags", [])}

        penalties = {
            "ASSISTANT_IN_LOOP": 20,
            "ASSISTANT_REPLY_IMPROPER": 25,
            "DEAD_AIR": 10,
            "USER_FRUSTRATED": 15,
            "ASSISTANT_LACKS_EMPATHY": 10,
            "PIPELINE_ERROR": 15,
        }
        for tag, penalty in penalties.items():
            if tag in tag_names:
                score -= penalty
                flags.append(tag.lower())

        errors = int(ctx.get("pipeline_error_count") or 0)
        if errors:
            score -= min(errors * 10, 30)
            flags.append("pipeline_errors")

        qa_scores = ctx.get("qa_scores") or []
        if qa_scores:
            mapped = sum(min(max(s, 1), 10) / 10.0 * 100 for s in qa_scores) / len(qa_scores)
            score = score * 0.4 + mapped * 0.6

        bot_count = len(ctx.get("bot_utterances") or [])
        user_count = len(ctx.get("user_utterances") or [])
        if bot_count == 0 and user_count > 0:
            score -= 30
            flags.append("no_bot_responses")

        return DimensionScore(
            dimension=QualityDimension.RESPONSE_QUALITY,
            score=_clamp(score),
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.RESPONSE_QUALITY],
            evidence={
                "qa_tag_count": len(tag_names),
                "pipeline_errors": errors,
                "qa_llm_scores": qa_scores,
            },
            flags=flags,
        )

    def score_interruption_handling(self, ctx: dict[str, Any]) -> DimensionScore:
        data = ctx.get("interruptions") or {}
        total = int(data.get("total") or 0)
        handled = int(data.get("handled_within_3s") or 0)

        if total == 0:
            score = 100.0
            flags = ["no_interruptions"]
        else:
            ratio = handled / total
            score = 40.0 + ratio * 60.0
            flags = []
            if ratio < 0.5:
                flags.append("poor_interruption_recovery")

        return DimensionScore(
            dimension=QualityDimension.INTERRUPTION_HANDLING,
            score=_clamp(score),
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.INTERRUPTION_HANDLING],
            evidence=data,
            flags=flags,
        )

    def score_payment_negotiation(self, ctx: dict[str, Any]) -> DimensionScore:
        outcome = (ctx.get("negotiation_outcome") or "").lower()
        collected = bool(ctx.get("payment_collected"))
        flags: list[str] = []

        if collected or outcome in {"accepted", "paid", "success", "committed"}:
            score = 95.0
        elif outcome in {"counter_offer", "partial", "installment", "scheduled"}:
            score = 75.0
        elif outcome in {"declined", "rejected", "failed"}:
            score = 35.0
            flags.append("negotiation_failed")
        elif outcome in {"pending", "", "none"}:
            score = 55.0
            flags.append("no_negotiation_outcome")
        else:
            score = 50.0

        disposition = (ctx.get("disposition") or "").lower()
        if "payment" in disposition and collected:
            score = max(score, 90.0)

        return DimensionScore(
            dimension=QualityDimension.PAYMENT_NEGOTIATION,
            score=_clamp(score),
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.PAYMENT_NEGOTIATION],
            evidence={
                "negotiation_outcome": outcome,
                "payment_collected": collected,
                "disposition": ctx.get("disposition"),
            },
            flags=flags,
        )

    def score_latency(self, ctx: dict[str, Any]) -> DimensionScore:
        metrics = ctx.get("call_metrics") or {}
        avg_latency = metrics.get("avg_latency_seconds")
        avg_ttfb = metrics.get("avg_ttfb_seconds")
        max_latency = metrics.get("max_latency_seconds")
        flags: list[str] = []

        latency_score = _latency_band(avg_latency, good=1.0, ok=2.0, poor=3.5)
        ttfb_score = _latency_band(avg_ttfb, good=0.8, ok=1.5, poor=2.5)
        max_score = _latency_band(max_latency, good=2.0, ok=4.0, poor=6.0)

        if avg_latency is None and avg_ttfb is None:
            score = 70.0
            flags.append("no_latency_samples")
        else:
            parts = [s for s in (latency_score, ttfb_score, max_score) if s is not None]
            score = sum(parts) / len(parts) if parts else 70.0
            if score < 60:
                flags.append("high_latency")

        return DimensionScore(
            dimension=QualityDimension.LATENCY,
            score=_clamp(score),
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.LATENCY],
            evidence=metrics,
            flags=flags,
        )

    def score_naturalness(self, ctx: dict[str, Any]) -> DimensionScore:
        bot = ctx.get("bot_utterances") or []
        user = ctx.get("user_utterances") or []
        flags: list[str] = []
        score = 80.0

        if bot:
            avg_len = sum(len(t) for t in bot) / len(bot)
            if avg_len > 280:
                score -= 15
                flags.append("long_bot_monologues")
            repeats = len(bot) - len(set(bot))
            if repeats > 0:
                score -= min(repeats * 8, 24)
                flags.append("repeated_bot_phrases")

        turns = len(user)
        duration = (ctx.get("call_metrics") or {}).get("call_duration_seconds")
        if duration and turns:
            sec_per_turn = float(duration) / max(len(user) + len(bot), 1)
            if sec_per_turn > 45:
                score -= 10
                flags.append("slow_pacing")

        tag_names = {t.get("tag", "") for t in ctx.get("qa_tags", [])}
        if "UNCLEAR_CONVERSATION" in tag_names:
            score -= 20
            flags.append("unclear_conversation")
        if "USER_DETECTS_AI" in tag_names:
            score -= 15
            flags.append("user_detects_ai")

        return DimensionScore(
            dimension=QualityDimension.CONVERSATIONAL_NATURALNESS,
            score=_clamp(score),
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.CONVERSATIONAL_NATURALNESS],
            evidence={
                "bot_turns": len(bot),
                "user_turns": len(user),
                "avg_bot_chars": round(sum(len(t) for t in bot) / len(bot), 1) if bot else 0,
            },
            flags=flags,
        )

    def score_escalation_correctness(self, ctx: dict[str, Any]) -> DimensionScore:
        escalated = bool(ctx.get("escalated"))
        tag_names = {t.get("tag", "") for t in ctx.get("qa_tags", [])}
        needs_escalation = bool(
            tag_names
            & {
                "USER_FRUSTRATED",
                "ASSISTANT_IN_LOOP",
                "USER_REQUESTING_FEATURE",
            }
        )
        flags: list[str] = []

        if escalated and needs_escalation:
            score = 95.0
        elif escalated and not needs_escalation:
            score = 65.0
            flags.append("possibly_unnecessary_escalation")
        elif not escalated and needs_escalation:
            score = 40.0
            flags.append("missed_escalation")
        else:
            score = 90.0

        disposition = (ctx.get("disposition") or "").lower()
        if "escalat" in disposition:
            score = max(score, 85.0 if escalated else 45.0)

        return DimensionScore(
            dimension=QualityDimension.ESCALATION_CORRECTNESS,
            score=_clamp(score),
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.ESCALATION_CORRECTNESS],
            evidence={
                "escalated": escalated,
                "needs_escalation_signals": needs_escalation,
                "disposition": ctx.get("disposition"),
            },
            flags=flags,
        )


def _clamp(value: float, *, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def _latency_band(
    value: float | None, *, good: float, ok: float, poor: float
) -> float | None:
    if value is None:
        return None
    if value <= good:
        return 100.0
    if value <= ok:
        return 80.0
    if value <= poor:
        return 55.0
    return 30.0


_engine: ConversationQualityScoringEngine | None = None


def get_scoring_engine() -> ConversationQualityScoringEngine:
    global _engine
    if _engine is None:
        _engine = ConversationQualityScoringEngine()
    return _engine
