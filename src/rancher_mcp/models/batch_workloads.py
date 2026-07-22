"""Typed models for curated Kubernetes batch/v1 reads.

Job and CronJob — the standard Kubernetes batch workload primitives
that the existing ``workloads`` pack (apps/v1: Deployments,
DaemonSets, StatefulSets) doesn't cover.
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_job_summaries() -> list["RancherJobSummary"]:
    """Return a typed empty Job summary list."""

    return []


def _empty_cron_job_summaries() -> list["RancherCronJobSummary"]:
    """Return a typed empty CronJob summary list."""

    return []


class RancherJobSummary(RancherModel):
    """Typed summary for one Kubernetes Job."""

    name: str = Field(
        default="<unknown-job>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    parallelism: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "parallelism"),
    )
    completions: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "completions"),
    )
    backoff_limit: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "backoffLimit"),
    )
    active: int | None = Field(default=None, validation_alias=AliasPath("status", "active"))
    succeeded: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "succeeded"),
    )
    failed: int | None = Field(default=None, validation_alias=AliasPath("status", "failed"))
    start_time: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "startTime"),
    )
    completion_time: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "completionTime"),
    )
    complete: bool | None = None
    failed_terminal: bool | None = None


class RancherJobDetail(RancherJobSummary):
    """Typed detail for one Kubernetes Job."""

    container_images: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherJobList(RancherModel):
    """Typed list response for Jobs in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    job_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    jobs: list[RancherJobSummary] = Field(default_factory=_empty_job_summaries)


class RancherCronJobSummary(RancherModel):
    """Typed summary for one Kubernetes CronJob."""

    name: str = Field(
        default="<unknown-cron-job>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    schedule: str | None = Field(default=None, validation_alias=AliasPath("spec", "schedule"))
    suspend: bool | None = Field(default=None, validation_alias=AliasPath("spec", "suspend"))
    concurrency_policy: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "concurrencyPolicy"),
    )
    successful_jobs_history_limit: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "successfulJobsHistoryLimit"),
    )
    failed_jobs_history_limit: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "failedJobsHistoryLimit"),
    )
    last_schedule_time: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "lastScheduleTime"),
    )
    last_successful_time: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "lastSuccessfulTime"),
    )
    active_job_count: int = 0


class RancherCronJobDetail(RancherCronJobSummary):
    """Typed detail for one Kubernetes CronJob."""

    container_images: list[str] = Field(default_factory=list)
    active_job_names: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherCronJobList(RancherModel):
    """Typed list response for CronJobs in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    cron_job_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cron_jobs: list[RancherCronJobSummary] = Field(
        default_factory=_empty_cron_job_summaries,
    )
