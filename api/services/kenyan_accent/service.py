"""Realtime Kenyan accent inference service."""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from loguru import logger

from api.services.kenyan_accent.classifier import AccentClassifier
from api.services.kenyan_accent.confidence import ConfidenceScorer
from api.services.kenyan_accent.config import KenyanAccentConfig, DEFAULT_KENYAN_ACCENT_CONFIG
from api.services.kenyan_accent.features import AccentFeatureExtractor
from api.services.kenyan_accent.preprocessing import PhoneAudioPreprocessor, pcm16_to_float32
from api.services.kenyan_accent.segmentation import SpeechSegmenter
from api.services.kenyan_accent.types import AccentClass, AccentPrediction, StreamingSessionState


class KenyanAccentInferenceService:
    """Stateful and stateless accent inference for phone-call PCM."""

    def __init__(self, config: KenyanAccentConfig = DEFAULT_KENYAN_ACCENT_CONFIG) -> None:
        self._config = config
        self._preprocessor = PhoneAudioPreprocessor(config)
        self._segmenter = SpeechSegmenter(config)
        self._extractor = AccentFeatureExtractor(config)
        self._classifier = AccentClassifier(config, self._extractor)
        self._scorer = ConfidenceScorer(config)
        self._sessions: dict[str, StreamingSessionState] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kenyan-accent")
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    async def classify_pcm(
        self,
        pcm: bytes,
        *,
        sample_rate: int = 16000,
        session_id: str | None = None,
    ) -> AccentPrediction | None:
        """Classify a PCM16 buffer (full utterance or sliding window)."""
        if not self._config.enabled:
            return None
        if not pcm:
            return None

        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    self._executor,
                    self._classify_sync,
                    pcm,
                    sample_rate,
                    session_id,
                    None,
                ),
                timeout=self._config.inference_timeout_s,
            )
        except asyncio.TimeoutError:
            logger.warning("Kenyan accent inference timed out session_id={}", session_id)
            return None

    async def push_chunk(
        self,
        session_id: str,
        pcm: bytes,
        *,
        sample_rate: int = 16000,
    ) -> AccentPrediction | None:
        """Append realtime PCM and classify when the sliding window is full."""
        if not self._config.enabled:
            return None

        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                state = StreamingSessionState(session_id=session_id, sample_rate=sample_rate)
                self._sessions[session_id] = state
            state.pcm_buffer.extend(pcm)
            state.total_audio_s += len(pcm) / (2 * sample_rate)

        window_samples = int(self._config.window_s * sample_rate) * 2
        if len(state.pcm_buffer) < window_samples:
            return state.last_prediction

        window_pcm = bytes(state.pcm_buffer[-window_samples:])
        hop_bytes = int(self._config.hop_s * sample_rate) * 2
        del state.pcm_buffer[: max(0, len(state.pcm_buffer) - window_samples + hop_bytes)]

        loop = asyncio.get_running_loop()
        try:
            prediction = await asyncio.wait_for(
                loop.run_in_executor(
                    self._executor,
                    self._classify_sync,
                    window_pcm,
                    sample_rate,
                    session_id,
                    state.prediction_history,
                ),
                timeout=self._config.inference_timeout_s,
            )
        except asyncio.TimeoutError:
            return state.last_prediction

        if prediction is not None:
            state.prediction_history.append(prediction.label)
            state.last_prediction = prediction
        return prediction

    async def start_session(self, *, sample_rate: int = 16000) -> str:
        session_id = uuid.uuid4().hex
        async with self._lock:
            self._sessions[session_id] = StreamingSessionState(
                session_id=session_id,
                sample_rate=sample_rate,
            )
        return session_id

    async def end_session(self, session_id: str) -> AccentPrediction | None:
        async with self._lock:
            state = self._sessions.pop(session_id, None)
        if state is None:
            return None
        if not state.pcm_buffer:
            return state.last_prediction
        return await self.classify_pcm(
            bytes(state.pcm_buffer),
            sample_rate=state.sample_rate,
            session_id=session_id,
        )

    async def get_session_result(self, session_id: str) -> AccentPrediction | None:
        async with self._lock:
            state = self._sessions.get(session_id)
            return state.last_prediction if state else None

    async def has_session(self, session_id: str) -> bool:
        async with self._lock:
            return session_id in self._sessions

    def _classify_sync(
        self,
        pcm: bytes,
        sample_rate: int,
        session_id: str | None,
        history: list[AccentClass] | None,
    ) -> AccentPrediction | None:
        wave = pcm16_to_float32(pcm)
        wave, sample_rate, snr_db = self._preprocessor.process(wave, sample_rate)

        speech_s = self._segmenter.speech_duration_s(wave, sample_rate)
        if speech_s < self._config.min_speech_s:
            return None

        mask = self._segmenter.speech_mask(wave, sample_rate)
        features = self._extractor.extract(wave, sample_rate, speech_mask=mask)
        scores = self._classifier.predict(features)
        entropy = AccentClassifier.entropy(scores)

        return self._scorer.score(
            scores,
            snr_db=snr_db,
            speech_ratio=features.speech_ratio,
            segment_duration_s=speech_s,
            model_entropy=entropy,
            pyannote_used=self._segmenter.pyannote_used,
            session_id=session_id,
            history=history,
        )

    async def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        async with self._lock:
            self._sessions.clear()


_service: KenyanAccentInferenceService | None = None


def get_kenyan_accent_service() -> KenyanAccentInferenceService:
    global _service
    if _service is None:
        _service = KenyanAccentInferenceService()
    return _service
