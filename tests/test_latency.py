from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dictate.latency import LatencyHistory, LatencySample


class LatencyHistoryTests(unittest.TestCase):
    @staticmethod
    def sample(engine: str = "parakeet", total: float = 100.0) -> LatencySample:
        return LatencySample(
            engine=engine,
            audio_ms=1_000,
            finalize_ms=5,
            inference_ms=total - 10,
            postprocess_ms=2,
            paste_ms=3,
            total_ms=total,
        )

    def test_renders_nearest_rank_percentiles(self) -> None:
        history = LatencyHistory()
        for total in (100.0, 200.0, 300.0, 400.0, 2_000.0):
            history.add(self.sample(total=total))

        report = history.render()

        self.assertIn("Release-to-paste p50: 300 ms", report)
        self.assertIn("Release-to-paste p95: 2000 ms", report)
        self.assertIn("parakeet (5): total p50/p95 300/2000 ms", report)
        self.assertIn("Latest engine: parakeet", report)

    def test_persists_capped_samples_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "latency.json"
            history = LatencyHistory(max_size=2, storage_path=path)
            history.add(self.sample(engine="whisper", total=500))
            history.add(self.sample(engine="parakeet", total=200))
            history.add(self.sample(engine="parakeet", total=100))

            restored = LatencyHistory(max_size=2, storage_path=path)

            self.assertEqual(
                [(sample.engine, sample.total_ms) for sample in restored.samples()],
                [("parakeet", 200.0), ("parakeet", 100.0)],
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], 1)
            self.assertNotIn("transcript", path.read_text(encoding="utf-8"))

    def test_clear_removes_samples_and_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "latency.json"
            history = LatencyHistory(storage_path=path)
            history.add(self.sample())

            history.clear()

            self.assertEqual(history.samples(), ())
            self.assertFalse(path.exists())

    def test_invalid_storage_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "latency.json"
            path.write_text('{"version":1,"samples":[{"engine":"whisper"}]}', encoding="utf-8")

            with self.assertLogs(level="WARNING"):
                history = LatencyHistory(storage_path=path)

            self.assertEqual(history.samples(), ())


if __name__ == "__main__":
    unittest.main()
