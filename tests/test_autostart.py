from __future__ import annotations

from pathlib import Path
import unittest

from dictate.autostart import LaunchAgentPaths, render_launch_agent


class AutostartTests(unittest.TestCase):
    def test_render_launch_agent_replaces_placeholders(self) -> None:
        rendered = render_launch_agent(
            LaunchAgentPaths(
                python=Path("/repo/.venv/bin/python3"),
                repo=Path("/repo"),
                home=Path("/Users/example"),
            )
        )

        self.assertIn("<string>/repo/.venv/bin/python3</string>", rendered)
        self.assertIn("<string>/repo</string>", rendered)
        self.assertIn("/Users/example/Library/Logs/dictate.log", rendered)
        self.assertNotIn("__PYTHON__", rendered)
        self.assertNotIn("__REPO__", rendered)
        self.assertNotIn("__HOME__", rendered)


if __name__ == "__main__":
    unittest.main()
