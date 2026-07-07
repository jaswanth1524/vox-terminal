from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

import numpy as np


SpeechTimestampFn = Callable[..., Sequence[dict[str, float]]]


@dataclass(frozen=True)
class VadDecision:
    should_stop: bool
    has_speech: bool
    trailing_silence_seconds: float


class SileroVadAutoStop:
    def __init__(
        self,
        *,
        silence_seconds: float = 1.0,
        min_speech_seconds: float = 0.25,
        get_speech_timestamps: SpeechTimestampFn | None = None,
        model: Any | None = None,
    ) -> None:
        self.silence_seconds = silence_seconds
        self.min_speech_seconds = min_speech_seconds
        self._get_speech_timestamps = get_speech_timestamps
        self._model = model

    def decide(self, audio: np.ndarray, *, sample_rate: int) -> VadDecision:
        if audio.size == 0:
            return VadDecision(False, False, 0.0)

        duration = audio.size / sample_rate
        timestamps = self._speech_timestamps(audio, sample_rate=sample_rate)
        speech_seconds = 0.0
        latest_speech_end = 0.0
        for timestamp in timestamps:
            start = float(timestamp["start"])
            end = float(timestamp["end"])
            speech_seconds += max(0.0, end - start)
            latest_speech_end = max(latest_speech_end, end)

        has_enough_speech = speech_seconds >= self.min_speech_seconds
        trailing_silence = max(0.0, duration - latest_speech_end)
        return VadDecision(
            should_stop=has_enough_speech and trailing_silence >= self.silence_seconds,
            has_speech=has_enough_speech,
            trailing_silence_seconds=trailing_silence if has_enough_speech else 0.0,
        )

    def _speech_timestamps(
        self,
        audio: np.ndarray,
        *,
        sample_rate: int,
    ) -> Sequence[dict[str, float]]:
        self._load()
        assert self._get_speech_timestamps is not None
        return self._get_speech_timestamps(
            audio.astype(np.float32, copy=False),
            self._model,
            sampling_rate=sample_rate,
            return_seconds=True,
        )

    def _load(self) -> None:
        if self._get_speech_timestamps is not None and self._model is not None:
            return
        from silero_vad import get_speech_timestamps, load_silero_vad

        self._get_speech_timestamps = get_speech_timestamps
        self._model = load_silero_vad()
