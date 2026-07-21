"""rancher-mcp package."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

__all__ = ["__version__"]

try:
    # The authoritative self-version: whatever is actually installed (what a
    # `uvx rancher-mcp` user is running). Beats a hardcoded literal that drifts.
    __version__ = _package_version("rancher-mcp")
except PackageNotFoundError:  # not installed (e.g. running from a raw checkout)
    __version__ = "0.0.0+unknown"
