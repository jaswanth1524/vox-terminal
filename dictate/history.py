from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import threading


@dataclass(frozen=True)
class HistoryEntry:
    text: str
    created_at: datetime


class TranscriptHistory:
    def __init__(self, max_size: int = 20) -> None:
        self.max_size = max_size
        self._entries: deque[HistoryEntry] = deque(maxlen=max_size or 0)
        self._lock = threading.Lock()

    def add(self, text: str, *, created_at: datetime | None = None) -> None:
        cleaned = text.strip()
        if not cleaned or self.max_size == 0:
            return
        entry = HistoryEntry(
            text=cleaned,
            created_at=created_at or datetime.now().astimezone(),
        )
        with self._lock:
            self._entries.appendleft(entry)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def entries(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._entries)

    def render(self) -> str:
        entries = self.entries()
        if not entries:
            return "No transcript history yet."
        lines: list[str] = []
        for index, entry in enumerate(entries, start=1):
            timestamp = entry.created_at.strftime("%H:%M:%S")
            lines.append(f"{index}. [{timestamp}] {entry.text}")
        return "\n".join(lines)
