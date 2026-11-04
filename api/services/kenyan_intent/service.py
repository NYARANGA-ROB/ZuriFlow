from __future__ import annotations

import asyncio
from typing import Any

from api.services.kenyan_intent.classifier import KenyanIntentClassifier
from api.services.kenyan_intent.config import DEFAULT_KENYAN_INTENT_CONFIG, KenyanIntentConfig
from api.services.kenyan_intent.confidence import ConfidenceScorer
from api.services.kenyan_intent.router import IntentRoutingEngine
from api.services.kenyan_intent.types import (
    BusinessIntent,
    ClassificationResult,
    IntentSessionState,
    RouteAction,
    RouteDecision,
    TranscriptKind,
)


def _default_normalizer(text: str) -> str:
    try:
        from api.services.kenyan_normalize.integration import normalize_transcript

        return normalize_transcript(text).normalized
    except Exception:
        return text


class RealtimeIntentInferenceService:
    """Per-session realtime intent inference with interruption-safe commits."""

    def __init__(self, config: KenyanIntentConfig | None = None) -> None:
        self._config = config or DEFAULT_KENYAN_INTENT_CONFIG
        self._classifier = KenyanIntentClassifier(
            self._config,
            normalizer=_default_normalizer if self._config.use_normalization else None,
            scorer=ConfidenceScorer(),
        )
        self._router = IntentRoutingEngine()
        self._sessions: dict[str, IntentSessionState] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def session(self, session_id: str) -> IntentSessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = IntentSessionState(session_id=session_id)
            self._locks[session_id] = asyncio.Lock()
        return self._sessions[session_id]

    async def infer(
        self,
        session_id: str,
        text: str,
        *,
        kind: TranscriptKind = TranscriptKind.FINAL,
    ) -> tuple[ClassificationResult, RouteDecision]:
        if not self._config.enabled:
            return self._disabled_result()

        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return self._infer_locked(session_id, text, kind=kind)

    def infer_sync(
        self,
        session_id: str,
        text: str,
        *,
        kind: TranscriptKind = TranscriptKind.FINAL,
    ) -> tuple[ClassificationResult, RouteDecision]:
        if not self._config.enabled:
            return self._disabled_result()
        return self._infer_locked(session_id, text, kind=kind)

    def _infer_locked(
        self,
        session_id: str,
        text: str,
        *,
        kind: TranscriptKind,
    ) -> tuple[ClassificationResult, RouteDecision]:
        state = self.session(session_id)
        is_partial = kind == TranscriptKind.PARTIAL

        if is_partial:
            state.partial_buffer = text.strip()

        result = self._classifier.classify(
            text,
            is_partial=is_partial,
            prior_intent=state.current_intent,
            prior_confidence=state.confidence,
        )
        result.is_partial = is_partial
        state.language = result.language

        commit = self._classifier.scorer.should_commit(
            result.confidence,
            is_partial=is_partial,
            partial_threshold=self._config.partial_confidence_threshold,
            final_threshold=self._config.final_confidence_threshold,
        )

        if not is_partial or (self._config.commit_on_partial and commit):
            if commit and result.intent != state.current_intent:
                if state.current_intent != BusinessIntent.UNKNOWN:
                    state.history.append(state.current_intent)
                    state.history = state.history[-self._config.max_history :]
                state.current_intent = result.intent
                state.confidence = result.confidence
            elif commit and result.intent == state.current_intent:
                state.confidence = max(state.confidence, result.confidence)

            state.slots.update({k: v for k, v in result.slots.items() if v})
            if not is_partial:
                state.partial_buffer = ""
                state.interrupted = False

        route = self._router.route(
            result,
            confidence_threshold=self._config.route_confidence_threshold,
            interrupted=state.interrupted and is_partial,
        )

        state.last_result = result
        state.last_route = route
        return result, route

    def on_interrupt(self, session_id: str, *, partial_text: str = "") -> IntentSessionState:
        state = self.session(session_id)
        state.interrupted = True
        if partial_text:
            state.partial_buffer = partial_text.strip()
        if state.current_intent != BusinessIntent.UNKNOWN:
            state.history.append(state.current_intent)
            state.history = state.history[-self._config.max_history :]
        state.current_intent = BusinessIntent.INTERRUPTION
        state.confidence = 0.95
        return state

    def on_resume(self, session_id: str) -> IntentSessionState:
        state = self.session(session_id)
        state.interrupted = False
        if state.history:
            state.current_intent = state.history[-1]
            state.confidence = self._classifier.scorer.decay_confidence(
                state.confidence,
                self._config.intent_confidence_decay,
            )
        else:
            state.current_intent = BusinessIntent.UNKNOWN
            state.confidence = 0.0
        return state

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def get_session_snapshot(self, session_id: str) -> dict[str, Any]:
        state = self._sessions.get(session_id)
        if not state:
            return {"session_id": session_id, "exists": False}
        data = state.to_dict()
        data["exists"] = True
        return data

    @staticmethod
    def _disabled_result() -> tuple[ClassificationResult, RouteDecision]:
        empty = ClassificationResult(intent=BusinessIntent.UNKNOWN, confidence=0.0)
        route = RouteDecision(
            action=RouteAction.CONTINUE,
            intent=BusinessIntent.UNKNOWN,
            confidence=0.0,
            priority=0,
            reason="Intent detection disabled",
        )
        return empty, route

    def end_session(self, session_id: str) -> dict[str, Any] | None:
        state = self._sessions.pop(session_id, None)
        self._locks.pop(session_id, None)
        return state.to_dict() if state else None


_service: RealtimeIntentInferenceService | None = None


def get_realtime_intent_service() -> RealtimeIntentInferenceService:
    global _service
    if _service is None:
        _service = RealtimeIntentInferenceService()
    return _service
