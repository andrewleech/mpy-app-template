"""Copier template for MicroPython application projects."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("mpy-app-template")
except PackageNotFoundError:
    # Running from a source tree without an installation.
    __version__ = "0.0.0+unknown"
