from __future__ import annotations

import unittest

from dictate.latency_benchmark import (
    EngineBenchmark,
    meets_fast_default_gate,
    should_promote_parakeet,
)


class LatencyBenchmarkTests(unittest.TestCase):
    def test_promotes_only_when_latency_and_accuracy_gates_pass(self) -> None:
        whisper = EngineBenchmark("whisper", (1_500, 2_500), 0.08)
        inaccurate = EngineBenchmark("parakeet", (300, 400), 0.16)
        accurate = EngineBenchmark("parakeet", (300, 400), 0.09)

        self.assertTrue(should_promote_parakeet(whisper, accurate))
        self.assertFalse(should_promote_parakeet(whisper, inaccurate))

    def test_fast_default_allows_bounded_accuracy_tradeoff(self) -> None:
        whisper = EngineBenchmark("whisper", (1_500, 2_500), 0.08)
        fast = EngineBenchmark("parakeet", (300, 400), 0.12)

        self.assertTrue(meets_fast_default_gate(whisper, fast))
        self.assertFalse(should_promote_parakeet(whisper, fast))

    def test_rejects_fast_median_with_slow_tail(self) -> None:
        whisper = EngineBenchmark("whisper", (1_500, 3_000), 0.08)
        parakeet = EngineBenchmark("parakeet", (300, 800), 0.08)

        self.assertFalse(meets_fast_default_gate(whisper, parakeet))
        self.assertFalse(should_promote_parakeet(whisper, parakeet))


if __name__ == "__main__":
    unittest.main()
