from __future__ import annotations

import unittest

from dictate.latency_benchmark import EngineBenchmark, should_promote_parakeet


class LatencyBenchmarkTests(unittest.TestCase):
    def test_promotes_only_when_latency_and_accuracy_gates_pass(self) -> None:
        whisper = EngineBenchmark("whisper", (1_500, 2_500), 0.08)
        fast = EngineBenchmark("parakeet", (500, 900), 0.09)
        inaccurate = EngineBenchmark("parakeet", (500, 900), 0.11)

        self.assertTrue(should_promote_parakeet(whisper, fast))
        self.assertFalse(should_promote_parakeet(whisper, inaccurate))

    def test_rejects_fast_median_with_slow_tail(self) -> None:
        whisper = EngineBenchmark("whisper", (1_500, 3_000), 0.08)
        parakeet = EngineBenchmark("parakeet", (500, 2_100), 0.08)

        self.assertFalse(should_promote_parakeet(whisper, parakeet))


if __name__ == "__main__":
    unittest.main()
