"""Per-descriptor module template context.

`ModuleContext` carries everything the `_generated_<id>.py` template
needs for one descriptor; `build_module_context` resolves it from the
descriptor (splitting the model import paths into module + class name).
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.codegen.descriptor import Descriptor

from .helpers import split_model_path


@dataclass(frozen=True)
class ModuleContext:
    """Template context for one descriptor's `_generated_<id>.py` file."""

    descriptor: Descriptor
    list_model_name: str
    detail_model_name: str

    def as_jinja_context(self) -> dict[str, object]:
        """Convert to a kwargs dict for Jinja's `template.render(**ctx)`."""

        descriptor = self.descriptor
        if descriptor.transport == "k8s-proxy":
            fetch_docstring_phrase = (
                f"{descriptor.display_name_plural} through Rancher's raw Kubernetes proxy"
            )
        elif descriptor.transport == "norman":
            fetch_docstring_phrase = f"the Rancher {descriptor.display_name_plural} collection"
        elif descriptor.namespaced:
            fetch_docstring_phrase = (
                f"the {descriptor.display_name_plural} collection for one namespace, "
                "or cluster-wide when namespace is omitted"
            )
        else:
            fetch_docstring_phrase = f"the {descriptor.display_name_plural} collection"
        return {
            "id": descriptor.id,
            "pack": descriptor.pack,
            "display_name_singular": descriptor.display_name_singular,
            "display_name_plural": descriptor.display_name_plural,
            "plane": descriptor.plane,
            "transport": descriptor.transport,
            "namespaced": descriptor.namespaced,
            "cluster_id_required": descriptor.cluster_id_required,
            "pagination": descriptor.pagination,
            "list_path": descriptor.list_path,
            "detail_path": descriptor.detail_path,
            "path_helper": descriptor.path_helper,
            "list_model_name": self.list_model_name,
            "detail_model_name": self.detail_model_name,
            "shared_imports": sorted(
                set(descriptor.shared_imports)
                | (
                    {descriptor.query_builder_function}
                    if descriptor.query_builder_in_shared
                    else set()
                )
            ),
            "support_value_imports": sorted(descriptor.support_value_imports),
            "summary_function": descriptor.summary_function,
            "query_builder_function": descriptor.query_builder_function,
            "query_builder_in_shared": descriptor.query_builder_in_shared,
            "operations": descriptor.operations,
            "list": descriptor.list_,
            "get": descriptor.get,
            "create": descriptor.create,
            "apply": descriptor.apply,
            "delete": descriptor.delete,
            "patches": descriptor.patches,
            "tools": descriptor.tools,
            "fetch_docstring_phrase": fetch_docstring_phrase,
        }


def build_module_context(descriptor: Descriptor) -> ModuleContext:
    """Resolve the template context for one descriptor module."""

    _, list_model_name = split_model_path(descriptor.list_response_model)
    _, detail_model_name = split_model_path(descriptor.detail_response_model)
    return ModuleContext(
        descriptor=descriptor,
        list_model_name=list_model_name,
        detail_model_name=detail_model_name,
    )
