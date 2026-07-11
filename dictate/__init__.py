"""Local macOS push-to-talk dictation."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("vox-terminal")
except PackageNotFoundError:
    __version__ = "0+unknown"
