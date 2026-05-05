"""Application configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import cast

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from rancher_mcp.models.discovery import RancherInstanceConfig


class AppSettings(BaseSettings):
    """Top-level application settings."""

    default_instance: str = Field(default="default", alias="RANCHER_DEFAULT_INSTANCE")
    catalog_path: str = Field(default="catalog/capabilities.yaml", alias="RANCHER_MCP_CATALOG_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    instances_json: str | None = Field(default=None, alias="RANCHER_INSTANCES_JSON")
    rancher_url: str | None = Field(default=None, alias="RANCHER_URL")
    rancher_token: str | None = Field(default=None, alias="RANCHER_TOKEN")
    rancher_verify_ssl: bool = Field(default=True, alias="RANCHER_VERIFY_SSL")
    rancher_ca_bundle: str | None = Field(default=None, alias="RANCHER_CA_BUNDLE")
    rancher_read_only: bool = Field(default=False, alias="RANCHER_READ_ONLY")
    server_name: str = Field(default="rancher-mcp", alias="RANCHER_MCP_SERVER_NAME")
    server_instructions: str = Field(
        default="Capability-aware Rancher MCP server for Rancher 2.6.5",
        alias="RANCHER_MCP_SERVER_DESCRIPTION",
    )
    instances: dict[str, RancherInstanceConfig] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def build_instances(self) -> AppSettings:
        """Normalize single-instance and multi-instance configuration."""

        instances: dict[str, RancherInstanceConfig] = {}

        if self.instances_json:
            try:
                raw_instances: object = json.loads(self.instances_json)
            except json.JSONDecodeError as exc:  # pragma: no cover - validation branch
                raise ValueError("RANCHER_INSTANCES_JSON must be valid JSON") from exc

            if not isinstance(raw_instances, dict):
                raise ValueError("RANCHER_INSTANCES_JSON must decode to an object")

            typed_instances = cast(dict[str, object], raw_instances)
            for name, payload in typed_instances.items():
                if not isinstance(payload, dict):
                    raise ValueError(f"Instance {name!r} must decode to an object")
                typed_payload = cast(dict[str, object], payload)
                instances[name] = RancherInstanceConfig.model_validate(typed_payload)

        if self.rancher_url and self.rancher_token:
            instances.setdefault(
                self.default_instance,
                RancherInstanceConfig(
                    url=self.rancher_url,
                    token=SecretStr(self.rancher_token),
                    verify_ssl=self.rancher_verify_ssl,
                    ca_bundle=self.rancher_ca_bundle,
                    read_only=self.rancher_read_only,
                ),
            )

        if not instances:
            raise ValueError(
                "Configure either RANCHER_INSTANCES_JSON or the single-instance "
                "RANCHER_URL/RANCHER_TOKEN settings"
            )

        if self.default_instance not in instances:
            raise ValueError(
                f"Default instance {self.default_instance!r} is not present in configured instances"
            )

        self.instances = instances
        return self


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Load settings from environment and cache them."""

    return AppSettings()


def clear_settings_cache() -> None:
    """Clear cached settings for tests or controlled reloads."""

    get_settings.cache_clear()


def validate_startup_settings() -> AppSettings:
    """Validate settings eagerly for application startup."""

    try:
        return get_settings()
    except ValidationError as exc:  # pragma: no cover - defensive startup behavior
        raise RuntimeError("Invalid application configuration") from exc
