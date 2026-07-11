from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from dictate.latency_benchmark import BenchmarkCase
from dictate.performance_audit import (
    BUNDLE_SIZE_BUDGET_BYTES,
    PerformanceAudit,
    _parse_memory_size,
    audit_engine,
    directory_size,
)


class FakeEngine:
    name = "parakeet"

    def __init__(self) -> None:
        self.loads = 0
        self.calls = 0

    def load(self) -> None:
        self.loads += 1

    def transcribe(self, audio: np.ndarray) -> str:
        del audio
        self.calls += 1
        return "hello"


class PerformanceAuditTests(unittest.TestCase):
    def test_audits_latency_memory_growth_and_bundle_size(self) -> None:
        engine = FakeEngine()
        times = iter(
            [
                0,
                10_000_000,
                10_000_000,
                110_000_000,
                110_000_000,
                310_000_000,
            ]
        )
        rss = iter([500_000_000, 510_000_000, 520_000_000, 520_000_000])
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = Path(temp_dir) / "App.app"
            bundle.mkdir()
            (bundle / "binary").write_bytes(b"x" * 10)
            result = audit_engine(
                engine,  # type: ignore[arg-type]
                [BenchmarkCase("hello", np.zeros(16, dtype=np.float32))],
                iterations=2,
                bundle_path=bundle,
                clock_ns=lambda: next(times),
                memory_reader=lambda: next(rss),
            )

        self.assertEqual(engine.loads, 1)
        self.assertEqual(engine.calls, 2)
        self.assertEqual(result.latency_iterations, 2)
        self.assertEqual(result.load_ms, 10)
        self.assertEqual(result.p50_ms, 100)
        self.assertEqual(result.p95_ms, 200)
        self.assertEqual(result.memory_growth_bytes, 20_000_000)
        self.assertEqual(result.bundle_size_bytes, 10)
        self.assertTrue(result.passed)

    def test_failed_gate_fails_entire_audit(self) -> None:
        audit = PerformanceAudit(
            engine="parakeet",
            iterations=1,
            latency_iterations=1,
            load_ms=1,
            p50_ms=1,
            p95_ms=1,
            peak_memory_bytes=1,
            memory_growth_bytes=1,
            bundle_size_bytes=BUNDLE_SIZE_BUDGET_BYTES + 1,
            gates={"bundle_size": False},
        )

        self.assertFalse(audit.passed)

    def test_expected_missing_bundle_fails_bundle_gate(self) -> None:
        engine = FakeEngine()
        times = iter([0, 1_000_000, 1_000_000, 2_000_000])
        rss = iter([1, 1, 1])
        with tempfile.TemporaryDirectory() as temp_dir:
            result = audit_engine(
                engine,  # type: ignore[arg-type]
                [BenchmarkCase("hello", np.zeros(16, dtype=np.float32))],
                iterations=1,
                bundle_path=Path(temp_dir) / "Missing.app",
                clock_ns=lambda: next(times),
                memory_reader=lambda: next(rss),
            )

        self.assertIsNone(result.bundle_size_bytes)
        self.assertFalse(result.gates["bundle_size"])
        self.assertFalse(result.passed)

    def test_directory_size_counts_nested_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "nested").mkdir()
            (root / "one").write_bytes(b"12")
            (root / "nested" / "two").write_bytes(b"345")
            (root / "hard-link").hardlink_to(root / "one")

            self.assertEqual(directory_size(root), 5)

    def test_parses_vmmap_memory_units(self) -> None:
        self.assertEqual(_parse_memory_size("512K"), 512 * 1024)
        self.assertEqual(_parse_memory_size("1.5G"), round(1.5 * 1024**3))


if __name__ == "__main__":
    unittest.main()
