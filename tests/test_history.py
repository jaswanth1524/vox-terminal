from __future__ import annotations

import unittest
from datetime import datetime

from dictate.history import TranscriptHistory


class HistoryTests(unittest.TestCase):
    def test_adds_newest_entries_first_and_caps_size(self) -> None:
        history = TranscriptHistory(max_size=2)
        history.add("first", created_at=datetime(2026, 1, 1, 10, 0, 0))
        history.add("second", created_at=datetime(2026, 1, 1, 10, 0, 1))
        history.add("third", created_at=datetime(2026, 1, 1, 10, 0, 2))

        self.assertEqual([entry.text for entry in history.entries()], ["third", "second"])

    def test_ignores_empty_text_and_can_clear(self) -> None:
        history = TranscriptHistory(max_size=5)
        history.add("  ")
        history.add("hello")
        history.clear()

        self.assertEqual(history.entries(), [])
        self.assertEqual(history.render(), "No transcript history yet.")

    def test_render_includes_timestamps_and_text(self) -> None:
        history = TranscriptHistory(max_size=5)
        history.add("hello world", created_at=datetime(2026, 1, 1, 10, 30, 5))

        self.assertEqual(history.render(), "1. [10:30:05] hello world")


if __name__ == "__main__":
    unittest.main()
