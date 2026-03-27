"""Instance summarization helpers."""

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import ConfigurationError
from rancher_mcp.models.discovery import (
    InstanceList,
    InstanceSummary,
    RancherInstanceConfig,
    ServerProfile,
)


def resolve_instance(
    settings: AppSettings,
    instance_name: str | None = None,
) -> tuple[str, RancherInstanceConfig]:
    """Resolve a configured Rancher instance by name."""

    resolved_name = instance_name or settings.default_instance
    try:
        return resolved_name, settings.instances[resolved_name]
    except KeyError as exc:
        raise ConfigurationError(f"Unknown Rancher instance {resolved_name!r}") from exc


def build_instance_list(settings: AppSettings, primary_target_version: str) -> InstanceList:
    """Build a public instance inventory from settings."""

    instances = [
        InstanceSummary(
            name=name,
            url=config.url,
            verify_ssl=config.verify_ssl,
            read_only=config.read_only,
            is_default=name == settings.default_instance,
        )
        for name, config in sorted(settings.instances.items())
    ]
    return InstanceList(
        default_instance=settings.default_instance,
        primary_target_version=primary_target_version,
        instances=instances,
    )


def build_server_profile(settings: AppSettings, primary_target_version: str) -> ServerProfile:
    """Build a compact server profile."""

    return ServerProfile(
        project_name="rancher-mcp",
        default_instance=settings.default_instance,
        primary_target_version=primary_target_version,
        catalog_path=settings.catalog_path,
        multi_instance_enabled=len(settings.instances) > 1,
    )
