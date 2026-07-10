from __future__ import annotations

import unittest

from dictate.latency import LatencyHistory, LatencySample


class LatencyHistoryTests(unittest.TestCase):
    def test_renders_nearest_rank_percentiles(self) -> None:
        history = LatencyHistory()
        for total in (100.0, 200.0, 300.0, 400.0, 2_000.0):
            history.add(
                LatencySample(
                    engine="parakeet",
                    audio_ms=1_000,
                    finalize_ms=5,
                    inference_ms=total - 10,
                    postprocess_ms=2,
                    paste_ms=3,
                    total_ms=total,
                )
            )

        report = history.render()

        self.assertIn("Release-to-paste p50: 300 ms", report)
        self.assertIn("Release-to-paste p95: 2000 ms", report)
        self.assertIn("Latest engine: parakeet", report)


if __name__ == "__main__":
    unittest.main()
