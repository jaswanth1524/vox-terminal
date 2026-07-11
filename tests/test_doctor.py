from __future__ import annotations

import unittest

from dictate.doctor import permission_target_description


class DoctorTests(unittest.TestCase):
    def test_frozen_app_reports_bundle_as_permission_target(self) -> None:
        target = permission_target_description(
            executable=(
                "/Users/example/Applications/Vox Terminal.app/Contents/MacOS/Vox Terminal"
            ),
            frozen=True,
        )

        self.assertEqual(target, "/Users/example/Applications/Vox Terminal.app")

    def test_source_run_reports_terminal_and_virtual_environment(self) -> None:
        target = permission_target_description(
            executable="/repo/.venv/bin/python",
            frozen=False,
        )

        self.assertEqual(
            target,
            "the launching terminal app and virtual-environment Python",
        )


if __name__ == "__main__":
    unittest.main()
