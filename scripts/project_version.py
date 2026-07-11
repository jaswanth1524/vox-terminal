#!/usr/bin/env python3
"""Print the release version from the project's single source of truth."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

with (ROOT / "pyproject.toml").open("rb") as project_file:
    print(tomllib.load(project_file)["project"]["version"])
