from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class VadDecision:
    should_stop: bool
    has_speech: bool
    trailing_silence_seconds: float


@dataclass(frozen=True)
class VadState:
    """A small, immutable snapshot of the streaming detector state."""

    decision: VadDecision
    processed_seconds: float
    voiced_seconds: float
    noise_floor: float
    speech_threshold: float
    pending_samples: int


class StreamingEnergyVad:
    """Incremental RMS-energy VAD with constant retained memory.

    Audio passed to :meth:`process` is new audio only. The detector reduces it to
    counters and a short, incomplete analysis frame; it never retains recording
    history. A brief initial calibration period learns the ambient noise floor.
    """

    def __init__(
        self,
        *,
        silence_seconds: float = 1.0,
        min_speech_seconds: float = 0.25,
        speech_rms_threshold: float = 0.002,
        noise_multiplier: float = 3.0,
        frame_seconds: float = 0.02,
        calibration_seconds: float = 0.1,
        noise_smoothing: float = 0.05,
    ) -> None:
        if silence_seconds <= 0:
            raise ValueError("silence_seconds must be positive")
        if min_speech_seconds < 0:
            raise ValueError("min_speech_seconds must be non-negative")
        if speech_rms_threshold < 0:
            raise ValueError("speech_rms_threshold must be non-negative")
        if noise_multiplier <= 0:
            raise ValueError("noise_multiplier must be positive")
        if frame_seconds <= 0:
            raise ValueError("frame_seconds must be positive")
        if calibration_seconds < 0:
            raise ValueError("calibration_seconds must be non-negative")
        if not 0 < noise_smoothing <= 1:
            raise ValueError("noise_smoothing must be in the range (0, 1]")

        self.silence_seconds = silence_seconds
        self.min_speech_seconds = min_speech_seconds
        self.speech_rms_threshold = speech_rms_threshold
        self.noise_multiplier = noise_multiplier
        self.frame_seconds = frame_seconds
        self.calibration_seconds = calibration_seconds
        self.noise_smoothing = noise_smoothing
        self.reset()

    def reset(self) -> None:
        """Forget the previous recording while retaining detector settings."""

        self._sample_rate: int | None = None
        self._frame_samples = 0
        self._calibration_target_samples = 0
        self._calibration_samples = 0
        self._calibration_noise_frames = 0
        self._processed_samples = 0
        self._voiced_samples = 0
        self._trailing_silence_samples = 0
        self._noise_floor = 0.0
        self._pending = np.empty(0, dtype=np.float32)

    def process(self, audio: np.ndarray, *, sample_rate: int) -> VadDecision:
        """Consume one new audio chunk and return the current auto-stop decision."""

        self._configure_sample_rate(sample_rate)
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return self.decision()

        if self._pending.size:
            needed = self._frame_samples - self._pending.size
            if samples.size < needed:
                self._pending = np.concatenate((self._pending, samples))
                return self.decision()

            frame = np.empty(self._frame_samples, dtype=np.float32)
            split = self._pending.size
            frame[:split] = self._pending
            frame[split:] = samples[:needed]
            self._process_frame(frame)
            self._pending = np.empty(0, dtype=np.float32)
            samples = samples[needed:]

        complete_samples = (samples.size // self._frame_samples) * self._frame_samples
        if complete_samples:
            frames = samples[:complete_samples].reshape(-1, self._frame_samples)
            for frame in frames:
                self._process_frame(frame)

        if complete_samples < samples.size:
            self._pending = samples[complete_samples:].copy()

        return self.decision()

    def decide(self, audio: np.ndarray, *, sample_rate: int) -> VadDecision:
        """Compatibility wrapper; ``audio`` must contain new samples only."""

        return self.process(audio, sample_rate=sample_rate)

    def decision(self) -> VadDecision:
        """Return the latest decision without consuming audio."""

        if self._sample_rate is None:
            return VadDecision(False, False, 0.0)

        voiced_seconds = self._voiced_samples / self._sample_rate
        has_speech = self._voiced_samples > 0 and voiced_seconds >= self.min_speech_seconds
        if not has_speech:
            return VadDecision(False, False, 0.0)

        trailing_silence_seconds = self._trailing_silence_samples / self._sample_rate
        return VadDecision(
            should_stop=trailing_silence_seconds >= self.silence_seconds,
            has_speech=True,
            trailing_silence_seconds=trailing_silence_seconds,
        )

    def state(self) -> VadState:
        """Return diagnostic counters without exposing or copying audio history."""

        sample_rate = self._sample_rate or 1
        return VadState(
            decision=self.decision(),
            processed_seconds=self._processed_samples / sample_rate,
            voiced_seconds=self._voiced_samples / sample_rate,
            noise_floor=self._noise_floor,
            speech_threshold=self._current_threshold(),
            pending_samples=int(self._pending.size),
        )

    def _configure_sample_rate(self, sample_rate: int) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self._sample_rate is not None:
            if sample_rate != self._sample_rate:
                raise ValueError("sample_rate cannot change without reset()")
            return

        self._sample_rate = sample_rate
        self._frame_samples = max(1, round(self.frame_seconds * sample_rate))
        self._calibration_target_samples = round(self.calibration_seconds * sample_rate)

    def _process_frame(self, frame: np.ndarray) -> None:
        rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))
        if not np.isfinite(rms):
            rms = 0.0

        frame_samples = int(frame.size)
        self._processed_samples += frame_samples
        in_calibration = self._calibration_samples < self._calibration_target_samples
        self._calibration_samples += frame_samples

        if rms > self._current_threshold():
            self._voiced_samples += frame_samples
            self._trailing_silence_samples = 0
            return

        self._trailing_silence_samples += frame_samples
        if in_calibration:
            self._calibration_noise_frames += 1
            weight = 1.0 / self._calibration_noise_frames
            self._noise_floor += weight * (rms - self._noise_floor)
        else:
            self._noise_floor += self.noise_smoothing * (rms - self._noise_floor)

    def _current_threshold(self) -> float:
        return max(self.speech_rms_threshold, self._noise_floor * self.noise_multiplier)


# Preserve the original import while callers migrate to the implementation-neutral name.
SileroVadAutoStop = StreamingEnergyVad
