"""CLI entrypoint."""

from rancher_mcp.config import validate_startup_settings
from rancher_mcp.logging import configure_logging
from rancher_mcp.server import mcp
from rancher_mcp.services.catalog import get_capability_catalog


def main() -> None:
    """Validate startup dependencies and launch the server."""

    settings = validate_startup_settings()
    configure_logging(settings.log_level)
    get_capability_catalog(settings.catalog_path)
    mcp.run()


if __name__ == "__main__":
    main()
