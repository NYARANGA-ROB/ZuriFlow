"""Speech segmentation with pyannote (optional) and energy fallback."""

from __future__ import annotations

import numpy as np
from loguru import logger

from api.services.kenyan_accent.config import KenyanAccentConfig
from api.services.kenyan_accent.types import SpeechSegment


class SpeechSegmenter:
    """Gate accent inference to speech regions in noisy phone audio."""

    def __init__(self, config: KenyanAccentConfig) -> None:
        self._config = config
        self._pyannote_pipeline = None
        self._pyannote_available = False
        self._init_pyannote()

    @property
    def pyannote_used(self) -> bool:
        return self._pyannote_available

    def _init_pyannote(self) -> None:
        if not self._config.pyannote_token:
            return
        try:
            from pyannote.audio.pipelines import VoiceActivityDetection

            pipeline = VoiceActivityDetection(
                segmentation=self._config.pyannote_segmentation_model,
                use_auth_token=self._config.pyannote_token,
            )
            pipeline.instantiate(
                {
                    "min_duration_on": self._config.pyannote_min_speech_s,
                    "min_duration_off": self._config.pyannote_min_silence_s,
                }
            )
            self._pyannote_pipeline = pipeline
            self._pyannote_available = True
            logger.info("Kenyan accent: pyannote VAD loaded")
        except TypeError:
            try:
                from pyannote.audio.pipelines import VoiceActivityDetection

                pipeline = VoiceActivityDetection(
                    segmentation=self._config.pyannote_segmentation_model,
                )
                pipeline.instantiate(
                    {
                        "min_duration_on": self._config.pyannote_min_speech_s,
                        "min_duration_off": self._config.pyannote_min_silence_s,
                    }
                )
                self._pyannote_pipeline = pipeline
                self._pyannote_available = True
            except Exception as e:
                logger.warning("Kenyan accent: pyannote unavailable: {}", e)
        except Exception as e:
            logger.warning("Kenyan accent: pyannote unavailable, using energy VAD: {}", e)

    def speech_mask(self, wave: np.ndarray, sample_rate: int) -> np.ndarray:
        """Frame-level speech mask aligned to feature hop (1 = speech)."""
        if wave.size == 0:
            return np.zeros(0, dtype=np.float32)

        hop = self._config.hop_length
        n_frames = 1 + max(0, (len(wave) - self._config.win_length) // hop)
        mask = np.zeros(n_frames, dtype=np.float32)

        segments = self.segment(wave, sample_rate)
        for seg in segments:
            start_frame = seg.start_sample // hop
            end_frame = min(n_frames, (seg.end_sample + hop - 1) // hop)
            mask[start_frame:end_frame] = 1.0
        return mask

    def segment(self, wave: np.ndarray, sample_rate: int) -> list[SpeechSegment]:
        if wave.size == 0:
            return []

        if self._pyannote_pipeline is not None:
            try:
                return self._segment_pyannote(wave, sample_rate)
            except Exception as e:
                logger.debug("pyannote segmentation failed, falling back: {}", e)

        return self._segment_energy(wave, sample_rate)

    def _segment_pyannote(self, wave: np.ndarray, sample_rate: int) -> list[SpeechSegment]:
        import torch

        pipeline = self._pyannote_pipeline
        assert pipeline is not None
        tensor = torch.from_numpy(wave).float().unsqueeze(0)
        output = pipeline({"waveform": tensor, "sample_rate": sample_rate})

        segments: list[SpeechSegment] = []
        for speech in output.get_timeline().support():
            start = int(speech.start * sample_rate)
            end = int(speech.end * sample_rate)
            if end > start:
                segments.append(SpeechSegment(start_sample=start, end_sample=end))
        return segments

    def _segment_energy(self, wave: np.ndarray, sample_rate: int) -> list[SpeechSegment]:
        """Lightweight RMS VAD for telephony when pyannote is unavailable."""
        frame = max(1, int(0.02 * sample_rate))
        hop = max(1, frame // 2)
        energies = []
        for i in range(0, len(wave) - frame + 1, hop):
            chunk = wave[i : i + frame]
            energies.append(float(np.sqrt(np.mean(chunk**2))))

        if not energies:
            return []

        threshold = max(np.percentile(energies, 60), 0.01)
        segments: list[SpeechSegment] = []
        in_speech = False
        start = 0
        min_samples = int(self._config.pyannote_min_speech_s * sample_rate)

        for idx, energy in enumerate(energies):
            pos = idx * hop
            if energy >= threshold:
                if not in_speech:
                    in_speech = True
                    start = pos
            elif in_speech:
                end = pos + frame
                if end - start >= min_samples:
                    segments.append(SpeechSegment(start_sample=start, end_sample=end))
                in_speech = False

        if in_speech:
            end = len(wave)
            if end - start >= min_samples:
                segments.append(SpeechSegment(start_sample=start, end_sample=end))

        return segments

    def speech_duration_s(self, wave: np.ndarray, sample_rate: int) -> float:
        total = sum(
            (seg.end_sample - seg.start_sample) / sample_rate
            for seg in self.segment(wave, sample_rate)
        )
        return total
