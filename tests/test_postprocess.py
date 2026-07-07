from __future__ import annotations

import unittest

from dictate.postprocess import clean_transcript


class PostprocessTests(unittest.TestCase):
    def test_strips_surrounding_whitespace(self) -> None:
        self.assertEqual(clean_transcript("  hello world  "), "hello world")

    def test_never_leaves_trailing_newline(self) -> None:
        cleaned = clean_transcript("run tests\n")
        self.assertEqual(cleaned, "run tests")
        self.assertFalse(cleaned.endswith("\n"))

    def test_filters_known_silence_hallucination(self) -> None:
        self.assertEqual(clean_transcript(" Thanks for watching! "), "")

    def test_filters_near_zero_rms(self) -> None:
        self.assertEqual(clean_transcript("hello", rms=0.0001), "")

    def test_keeps_text_above_rms_threshold(self) -> None:
        self.assertEqual(clean_transcript("hello", rms=0.01), "hello")


if __name__ == "__main__":
    unittest.main()
