"""Literal type aliases shared across the descriptor schema."""

from __future__ import annotations

from typing import Literal

Plane = Literal["norman", "steve"]
Transport = Literal["steve", "k8s-proxy", "norman"]
Operation = Literal["list", "get", "create", "apply", "patch", "delete"]
AnnotationSet = Literal[
    "READ_ONLY",
    "SAFE_WRITE",
    "IDEMPOTENT_WRITE",
    "DESTRUCTIVE",
    "UNKNOWN_ACTION",
]
FilterType = Literal["str", "bool"]
FilterPredicate = Literal["is_provided", "is_true"]
ArgType = Literal[
    "str",
    "int",
    "bool",
    "dict_str_str",
    "dict_str_object",
    "string_list",
]
