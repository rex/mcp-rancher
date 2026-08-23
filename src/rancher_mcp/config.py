"""Application configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import cast

from pydantic import Field, PrivateAttr, SecretStr, ValidationError, model_validator
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
    # The `instructions` string in the MCP handshake — the one place to state
    # what holds ACROSS tools, which no single tool description can carry.
    # Deliberately about relationships, defaults and hazards, not a manual:
    # per MCP's own guidance it should cover cross-tool relationships and
    # constraints, and Claude Code truncates past ~2000 bytes. Kept under that
    # ceiling by `test_server_instructions_fit_the_host_budget`.
    server_instructions: str = Field(
        default=(
            "Rancher MCP — capability-aware access to Rancher-managed Kubernetes. "
            "Targets Rancher 2.9.3; 2.6.5 stays supported via capability detection, "
            "so prefer discovery over assuming a version.\n"
            "\n"
            "TWO PLANES. Rancher exposes management objects (clusters, projects, "
            "users, RBAC, settings, catalogs) on the Norman /v3 API, and Kubernetes "
            "objects (pods, deployments, services, PVCs) on the Steve /v1 proxy. "
            "Tools are named for the object, not the plane; reach for the object you "
            "want. `rancher_{norman,steve}_resource_*` are the generic escape hatch "
            "for anything with no curated tool — they can read or mutate any resource "
            "either plane exposes.\n"
            "\n"
            "WHERE TO START. Broad question first: `rancher_clusters_health_summary` "
            "or `rancher_cluster_health_check` for cluster state; the `rancher_find_*` "
            "tools for what is broken right now (failing pods, unready nodes, stalled "
            "rollouts, unbound PVCs, blocking PDBs, endpointless services); "
            "`rancher_resource_events` for what happened to one object. Prefer one "
            "composite over many single gets.\n"
            "\n"
            'SCOPE ARGUMENTS ARE LOAD-BEARING. `cluster_id` defaults to "local" — the '
            "Rancher local cluster, NOT the cluster you were just looking at — so an "
            "omitted `cluster_id` silently targets the wrong cluster on a multi-cluster "
            "fleet. Always pass it explicitly. `instance` selects which Rancher server "
            "when several are configured. Omitting `namespace` on a list means "
            "cluster-wide, which is usually what triage wants.\n"
            "\n"
            "WRITES. Mutations are rate-limited and audited. Destructive tools take a "
            "required `confirmation` argument and refuse unless it exactly echoes the "
            "phrase the tool names — they do not act on a partial match and there is no "
            "dry-run form. Secret values are withheld unless a tool's `reveal` argument "
            "is set, and revealing is audited. Under RANCHER_READ_ONLY every mutating "
            "tool refuses.\n"
            "\n"
            "ERRORS are JSON objects, never prose: branch on `error_code` and retry "
            "only when `retryable` is true."
        ),
        alias="RANCHER_MCP_SERVER_DESCRIPTION",
    )
    write_rate_limit_per_min: int = Field(
        default=60,
        alias="RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN",
        description=(
            "Maximum write tool calls per minute across all instances. "
            "Burst capacity is twice this value. Set to 0 to disable."
        ),
    )
    # Computed from instances_json / the single-instance shorthand by the
    # model validator below — deliberately a PRIVATE attribute, not a
    # settings field. As a field it was env-bindable: with
    # case_sensitive=False, any stray `INSTANCES` environment variable
    # (a common shell word; GNU make also exports command-line vars like
    # `make live-health INSTANCES=lab` into recipe environments) bound to
    # it and pydantic-settings tried to JSON-parse the value, killing
    # startup with a SettingsError. Derived state must not be settable.
    _instances: dict[str, RancherInstanceConfig] = PrivateAttr(
        default_factory=dict[str, RancherInstanceConfig]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def instances(self) -> dict[str, RancherInstanceConfig]:
        """Resolved instance map (name -> config). Read-only, computed."""

        return self._instances

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

        self._instances = instances
        return self


class ToolsetSettings(BaseSettings):
    """Startup-time tool-surface selection — see ``rancher_mcp.toolsets``.

    Deliberately its OWN ``BaseSettings`` rather than three more fields on
    ``AppSettings``: ``AppSettings.build_instances`` raises when no Rancher
    instance is configured, but which TOOLS are on the wire is a process-shape
    decision independent of which Rancher server(s) are reachable.
    ``register_all_tools`` must be able to resolve the active toolset even when
    instance credentials are absent — which is exactly the case for most of
    this repo's own fleet-wide gates (``test_context_footprint.py``,
    ``test_no_plumbing_in_input_schemas.py``, the next-steps registry gate, the
    schema/dump parity gate, …), all of which build the real tool registry via
    ``register_all_tools`` with no ``RANCHER_URL``/``RANCHER_TOKEN`` set at
    all. Coupling toolset resolution to ``AppSettings`` would make every one of
    those raise ``ValidationError`` in CI, where `.github/workflows/validate.yml`
    sets no instance credentials whatsoever (unlike `release.yml`'s smoke job).
    """

    toolsets: str = Field(default="all", alias="RANCHER_TOOLSETS")
    include_tools: str = Field(default="", alias="RANCHER_TOOLS")
    exclude_tools: str = Field(default="", alias="RANCHER_EXCLUDE_TOOLS")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Load settings from environment and cache them."""

    return AppSettings()


def clear_settings_cache() -> None:
    """Clear cached settings for tests or controlled reloads."""

    get_settings.cache_clear()


@lru_cache(maxsize=1)
def get_toolset_settings() -> ToolsetSettings:
    """Load toolset-selection settings from environment and cache them."""

    return ToolsetSettings()


def clear_toolset_settings_cache() -> None:
    """Clear cached toolset settings for tests or controlled reloads."""

    get_toolset_settings.cache_clear()


def validate_startup_settings() -> AppSettings:
    """Validate settings eagerly for application startup."""

    try:
        return get_settings()
    except ValidationError as exc:  # pragma: no cover - defensive startup behavior
        raise RuntimeError("Invalid application configuration") from exc
