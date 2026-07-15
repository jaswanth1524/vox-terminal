#!/usr/bin/env python3
"""Repeat deterministic fault-injection tests for crash-prone app boundaries."""

from __future__ import annotations

import argparse
import sys
import unittest

CRASH_BOUNDARY_PATTERNS = (
    "test_hotkey.py",
    "test_recorder.py",
    "test_service.py",
    "test_controller.py",
    "test_menubar.py",
    "test_logging_config.py",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iterations",
        type=int,
        default=25,
        help="number of complete crash-boundary test cycles (default: 25)",
    )
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error("--iterations must be positive")

    completed_tests = 0
    for iteration in range(1, args.iterations + 1):
        suite = unittest.TestSuite(
            unittest.defaultTestLoader.discover("tests", pattern=pattern)
            for pattern in CRASH_BOUNDARY_PATTERNS
        )
        count = suite.countTestCases()
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=0).run(suite)
        if not result.wasSuccessful():
            print(f"Crash feedback loop failed in cycle {iteration}/{args.iterations}.")
            return 1
        completed_tests += count
        print(f"Crash feedback cycle {iteration}/{args.iterations}: {count} checks passed")

    print(
        f"Crash feedback loop passed: {completed_tests} checks across "
        f"{args.iterations} cycles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
