"""Tests for capture-sweep's tool-registry enumeration (no live lab needed).

``build_capture_plan`` itself needs a fully-registered FastMCP instance
(every ``rancher_mcp`` tool module) and is exercised end-to-end whenever
``make capture-sweep`` runs against the lab, so it is not re-tested here.
This file targets ``resolve_impl_fn`` in isolation — the one load-bearing
mechanism most worth pinning down with a unit test: given a wrapped,
registered tool function, it must recover the pristine impl, never the
wrapper the ``apply_*_to_all_tools`` passes leave behind.

Every fixture function below is created fresh inside its own test (never
shared at module scope) so mutating ``__module__`` for the test can never
leak into another test.
"""

from __future__ import annotations

import functools
import sys
import types

from devtools.capture_sweep import resolve_impl_fn


def test_resolve_impl_fn_recovers_the_pristine_impl_not_the_wrapped_registered_fn() -> None:
    """The wrapper's __module__/__name__ must lead back to the real impl fn."""

    module_name = "_capture_sweep_fixture_module_a"
    module = types.ModuleType(module_name)

    def impl(*, settings: object = None, instance: object = None) -> str:
        """Stand-in for a real tool's impl fn: accepts settings/instance directly."""

        del settings, instance
        return "impl-result"

    impl.__module__ = module_name
    module.rancher_fake_get = impl

    @functools.wraps(impl)
    def wrapper() -> object:
        # Simulates apply_metrics_to_all_tools / apply_structured_errors_to_all_tools:
        # a functools.wraps-preserving layer that does NOT forward settings/instance
        # (calling it with those kwargs would raise TypeError, like the real
        # registered ``*_tool`` wrapper does).
        return impl()

    sys.modules[module_name] = module
    try:
        resolved = resolve_impl_fn(wrapper, "rancher_fake_get")

        assert resolved is impl
        assert resolved is not wrapper
        assert resolved(settings=object(), instance="current") == "impl-result"
    finally:
        del sys.modules[module_name]


def test_resolve_impl_fn_falls_back_to_the_wrapper_when_no_separate_impl_exists() -> None:
    """A tool registered directly (no ``_tool`` split) should resolve to itself."""

    module_name = "_capture_sweep_fixture_module_b"
    module = types.ModuleType(module_name)
    # Deliberately no attributes set on the module — nothing else to recover.

    def fn() -> str:
        return "ok"

    fn.__module__ = module_name

    sys.modules[module_name] = module
    try:
        resolved = resolve_impl_fn(fn, "rancher_no_such_module_attribute")

        assert resolved is fn
    finally:
        del sys.modules[module_name]
