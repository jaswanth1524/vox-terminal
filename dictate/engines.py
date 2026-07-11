from __future__ import annotations

import gc
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from .config import DEFAULT_PARAKEET_BEAM_SIZE, AppConfig
from .mel import install_parakeet_librosa_shim
from .transcriber import Transcriber, configure_offline_mode


class TranscriptionEngine(Protocol):
    name: str

    def load(self) -> None: ...

    def transcribe(self, audio: np.ndarray) -> str: ...

    def close(self) -> None: ...


EngineLoader = Callable[[str], Any]
ArrayTranscribeImpl = Callable[[Any, np.ndarray, int], str]
QuantizeImpl = Callable[[Any, int], None]


def _load_parakeet(model: str) -> Any:
    install_parakeet_librosa_shim()
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


def _quantize_parakeet(backend: Any, bits: int) -> None:
    import mlx.core as mx
    import mlx.nn as nn

    nn.quantize(backend, group_size=64, bits=bits)
    mx.eval(backend.parameters())
    gc.collect()
    mx.clear_cache()


@dataclass
class ParakeetEngine:
    model: str
    offline: bool = True
    beam_size: int = DEFAULT_PARAKEET_BEAM_SIZE
    quantization_bits: int | None = None
    loader: EngineLoader = _load_parakeet
    transcribe_impl: ArrayTranscribeImpl = _transcribe_parakeet_array
    quantize_impl: QuantizeImpl = _quantize_parakeet
    name: str = field(default="parakeet", init=False)
    _backend: Any | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        configure_offline_mode(offline=self.offline)

    def load(self) -> None:
        if self._backend is not None:
            return
        self._backend = self.loader(self.model)
        if self.quantization_bits is not None:
            self.quantize_impl(self._backend, self.quantization_bits)
        # Compile the bounded shapes used by short dictation before reporting ready.
        for seconds in (2, 4, 8):
            self._transcribe_array(np.zeros(16_000 * seconds, dtype=np.float32))

    def transcribe(self, audio: np.ndarray) -> str:
        self.load()
        return self._transcribe_array(audio)

    def close(self) -> None:
        self._backend = None
        gc.collect()
        try:
            import mlx.core as mx

            mx.clear_cache()
        except (ImportError, RuntimeError):
            pass

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
    model = _cached_model_path(config.selected_model)
    if config.engine == "whisper":
        return Transcriber(
            model=model,
            language=config.language,
            initial_prompt=config.whisper_initial_prompt,
            offline=True,
            temperature=0.0,
        )
    if config.engine == "parakeet":
        return ParakeetEngine(
            model=model,
            offline=True,
            beam_size=config.parakeet_beam_size,
            quantization_bits=config.parakeet_quantization_bits or None,
        )
    raise ValueError(f"Unsupported transcription engine: {config.engine}")


def _cached_model_path(model: str) -> str:
    from .model_manager import resolve_cached_model

    snapshot = resolve_cached_model(model)
    return str(snapshot) if snapshot is not None else model
