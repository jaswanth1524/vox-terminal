from __future__ import annotations

import re

KNOWN_SILENCE_HALLUCINATIONS = {
    "",
    ".",
    "...",
    "thank you",
    "thank you.",
    "thanks",
    "thanks.",
    "thanks for watching",
    "thanks for watching!",
    "you",
}


def clean_transcript(
    transcript: str | None,
    *,
    rms: float | None = None,
    silence_rms_threshold: float = 0.002,
) -> str:
    if rms is not None and rms <= silence_rms_threshold:
        return ""
    if transcript is None:
        return ""

    cleaned = transcript.strip().rstrip("\r\n")
    if _is_known_silence_hallucination(cleaned):
        return ""
    return cleaned


def _is_known_silence_hallucination(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.casefold()).strip()
    normalized = normalized.strip('"“”')
    return normalized in KNOWN_SILENCE_HALLUCINATIONS
