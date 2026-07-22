"""rancher-mcp package."""

# The authoritative self-version. `_version.py` is generated from the repo-root
# VERSION file by scripts/sync_versions.py and gated by pre-commit, so it is
# exact on every commit AND ships inside the wheel.
#
# It deliberately does NOT come from `importlib.metadata.version()`: that reads
# the installed *dist-info*, which for the editable install every developer and
# every `make dev` run uses only changes when the package is reinstalled. It
# silently reported a version several releases stale — an operator mid-incident
# could not tell whether their restart had actually picked up a fix.
from rancher_mcp._version import __version__

__all__ = ["__version__"]
