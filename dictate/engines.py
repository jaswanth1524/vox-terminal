from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from .config import AppConfig
from .transcriber import Transcriber, configure_offline_mode


class TranscriptionEngine(Protocol):
    name: str

    def load(self) -> None: ...

    def transcribe(self, audio: np.ndarray) -> str: ...


EngineLoader = Callable[[str], Any]
ArrayTranscribeImpl = Callable[[Any, np.ndarray, int], str]


def _load_parakeet(model: str) -> Any:
    from parakeet_mlx import from_pretrained

    return from_pretrained(model)


def _transcribe_parakeet_array(backend: Any, audio: np.ndarray, beam_size: int) -> str:
    import mlx.core as mx
    from parakeet_mlx import Beam, DecodingConfig, Greedy
    from parakeet_mlx.audio import get_logmel

    # parakeet_mlx.audio.load_audio also returns float32; get_logmel relies on
    # that width when viewing complex FFT output.
    samples = mx.array(audio.astype(np.float32, copy=False)).astype(mx.float32)
    mel = get_logmel(samples, backend.preprocessor_config)
    decoding = (
        Greedy()
        if beam_size == 1
        else Beam(
            beam_size=beam_size,
            length_penalty=0.013,
            patience=3.5,
            duration_reward=0.67,
        )
    )
    results = backend.generate(
        mel,
        decoding_config=DecodingConfig(decoding=decoding),
    )
    return str(results[0].text)


@dataclass
class ParakeetEngine:
    model: str
    offline: bool = True
    beam_size: int = 1
    loader: EngineLoader = _load_parakeet
    transcribe_impl: ArrayTranscribeImpl = _transcribe_parakeet_array
    name: str = field(default="parakeet", init=False)
    _backend: Any | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        configure_offline_mode(offline=self.offline)

    def load(self) -> None:
        if self._backend is not None:
            return
        self._backend = self.loader(self.model)
        # Compile the bounded shapes used by short dictation before reporting ready.
        for seconds in (2, 4, 8):
            self._transcribe_array(np.zeros(16_000 * seconds, dtype=np.float32))

    def transcribe(self, audio: np.ndarray) -> str:
        self.load()
        return self._transcribe_array(audio)

    def _transcribe_array(self, audio: np.ndarray) -> str:
        assert self._backend is not None
        sample_rate = int(self._backend.preprocessor_config.sample_rate)
        return self.transcribe_impl(
            self._backend,
            _pad_to_bucket(audio, sample_rate),
            self.beam_size,
        )


def _pad_to_bucket(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    for seconds in (2, 4, 8, 16, 32):
        target = sample_rate * seconds
        if audio.size <= target:
            return np.pad(audio, (0, target - audio.size))
    return audio


def build_engine(config: AppConfig) -> TranscriptionEngine:
    if config.engine == "whisper":
        return Transcriber(
            model=config.model,
            language=config.language,
            initial_prompt=config.whisper_initial_prompt,
            offline=True,
            temperature=0.0,
        )
    if config.engine == "parakeet":
        return ParakeetEngine(
            model=config.parakeet_model,
            offline=True,
            beam_size=config.parakeet_beam_size,
        )
    raise ValueError(f"Unsupported transcription engine: {config.engine}")
