from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd


class AudioCaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class Recording:
    audio: np.ndarray
    sample_rate: int
    started_at: float
    stopped_at: float

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.stopped_at - self.started_at)

    @property
    def rms(self) -> float:
        if self.audio.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(self.audio, dtype=np.float64))))


class Recorder:
    def __init__(
        self,
        *,
        sample_rate: int = 16_000,
        channels: int = 1,
        max_seconds: int = 120,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self._lock = threading.Lock()
        self._frames: list[np.ndarray] = []
        self._stream: Any | None = None
        self._started_at = 0.0
        self._max_samples = sample_rate * max_seconds
        self._sample_count = 0

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._frames = []
            self._sample_count = 0
            self._started_at = time.monotonic()
            try:
                sd.query_devices(kind="input")
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="float32",
                    callback=self._callback,
                )
                self._stream.start()
            except Exception as exc:
                self._stream = None
                self._frames = []
                self._sample_count = 0
                raise AudioCaptureError(
                    "Could not open the microphone input. Check Microphone "
                    "permission, reconnect the device, or choose a valid "
                    "default input device in macOS Sound settings."
                ) from exc

    def stop(self) -> Recording:
        with self._lock:
            stream = self._stream
            self._stream = None
            started_at = self._started_at

        stopped_at = time.monotonic()
        if stream is not None:
            try:
                stream.stop()
            except Exception as exc:
                print(f"audio stop warning: {exc}", flush=True)
            try:
                stream.close()
            except Exception as exc:
                print(f"audio close warning: {exc}", flush=True)

        with self._lock:
            if self._frames:
                audio = np.concatenate(self._frames).astype(np.float32, copy=False)
            else:
                audio = np.empty(0, dtype=np.float32)
            self._frames = []
            self._sample_count = 0

        return Recording(
            audio=audio.reshape(-1),
            sample_rate=self.sample_rate,
            started_at=started_at,
            stopped_at=stopped_at,
        )

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        del frames, time_info
        if status:
            print(f"audio capture warning: {status}", flush=True)

        chunk = indata[:, 0].copy()
        with self._lock:
            remaining = self._max_samples - self._sample_count
            if remaining <= 0:
                raise sd.CallbackStop
            if chunk.size > remaining:
                self._frames.append(chunk[:remaining])
                self._sample_count += remaining
                raise sd.CallbackStop
            self._frames.append(chunk)
            self._sample_count += chunk.size
