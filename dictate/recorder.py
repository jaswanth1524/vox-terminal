from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
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
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if channels <= 0:
            raise ValueError("channels must be positive")
        if max_seconds <= 0:
            raise ValueError("max_seconds must be positive")

        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self._lock = threading.Lock()
        self._stream: Any | None = None
        self._started_at = 0.0
        self._max_samples = sample_rate * max_seconds
        self._buffer = np.empty(self._max_samples, dtype=np.float32)
        self._sample_count = 0
        self._read_offset = 0

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._stream is not None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._sample_count = 0
            self._read_offset = 0
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
                self._sample_count = 0
                self._read_offset = 0
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
                # PortAudio's graceful stop waits for pending callbacks. That can
                # leave a menu-bar app looking frozen when a device disappears or
                # a callback stalls. Captured input is already in our own buffer,
                # so aborting is both lossless for Vox Terminal and bounded.
                stream.abort()
            except Exception as exc:
                logging.warning("Could not abort audio input: %s", exc)
            try:
                stream.close()
            except Exception as exc:
                logging.warning("Could not close audio input: %s", exc)

        with self._lock:
            audio = self._buffer[: self._sample_count].copy()
            self._sample_count = 0
            self._read_offset = 0

        return Recording(
            audio=audio.reshape(-1),
            sample_rate=self.sample_rate,
            started_at=started_at,
            stopped_at=stopped_at,
        )

    def snapshot(self) -> Recording:
        """Copy the recording so far.

        VAD polling should use :meth:`read_new_audio` to avoid repeatedly copying
        and processing the complete recording.
        """

        with self._lock:
            audio = self._buffer[: self._sample_count].copy()
            started_at = self._started_at
        return Recording(
            audio=audio.reshape(-1),
            sample_rate=self.sample_rate,
            started_at=started_at,
            stopped_at=time.monotonic(),
        )

    def read_new_audio(self) -> np.ndarray:
        """Return only samples captured since the previous read.

        The returned array owns its memory, so the audio callback can immediately
        continue writing into the fixed recording buffer.
        """

        with self._lock:
            start = self._read_offset
            stop = self._sample_count
            audio = self._buffer[start:stop].copy()
            self._read_offset = stop
        return audio

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        del frames, time_info
        if status:
            logging.warning("Audio capture warning: %s", status)

        chunk = np.asarray(indata[:, 0], dtype=np.float32)
        with self._lock:
            remaining = self._max_samples - self._sample_count
            if remaining <= 0:
                raise sd.CallbackStop
            write_count = min(chunk.size, remaining)
            write_end = self._sample_count + write_count
            self._buffer[self._sample_count : write_end] = chunk[:write_count]
            self._sample_count = write_end
            if write_count < chunk.size:
                raise sd.CallbackStop
