from __future__ import annotations

import importlib.metadata
import tomllib
import unittest
from pathlib import Path

from dictate import __version__


class VersionTests(unittest.TestCase):
    def test_package_and_project_versions_match(self) -> None:
        project_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with project_path.open("rb") as project_file:
            project_version = tomllib.load(project_file)["project"]["version"]

        self.assertEqual(__version__, importlib.metadata.version("vox-terminal"))
        self.assertEqual(__version__, project_version)


if __name__ == "__main__":
    unittest.main()
