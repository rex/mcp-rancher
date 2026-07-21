"""Pure Kubernetes-quantity math (ROADMAP L-2·0 / ADR-0002 rule #3).

Foundational and dependency-free so both the models layer and the tools layer
can derive human units, utilization percentages, and numeric comparisons from
raw Kubernetes quantities without either importing the other.
"""

from __future__ import annotations

# Binary (1024ⁿ) and decimal (1000ⁿ) Kubernetes quantity suffixes. The sub-unit
# ``m`` (milli, used for CPU) is handled separately below.
_BINARY = {"Ki": 1024**1, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4, "Pi": 1024**5}
_DECIMAL = {"k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15}
_MEM_UNITS = (("Ti", 1024**4), ("Gi", 1024**3), ("Mi", 1024**2), ("Ki", 1024))


def parse_quantity(quantity: str | None) -> float | None:
    """Parse a Kubernetes quantity (``4005204Ki``, ``1880m``, ``4``) to a float.

    Returns the value in base units — bytes for memory, cores for CPU (so
    ``1880m`` → ``1.88``). ``None`` on anything unparseable.
    """

    if not isinstance(quantity, str) or not quantity:
        return None
    text = quantity.strip()
    for suffix, factor in _BINARY.items():
        if text.endswith(suffix):
            return _to_float(text[: -len(suffix)], factor)
    if text.endswith("m"):  # milli (CPU): 1880m -> 1.88
        return _to_float(text[:-1], 1e-3)
    for suffix, factor in _DECIMAL.items():
        if text.endswith(suffix):
            return _to_float(text[: -len(suffix)], factor)
    return _to_float(text, 1.0)


def _to_float(number: str, factor: float) -> float | None:
    """Multiply a numeric string by a factor, or ``None`` if it isn't numeric."""

    try:
        return float(number) * factor
    except ValueError:
        return None


def humanize_memory(quantity: str | None) -> str | None:
    """Render a memory quantity in human binary units (``4005204Ki`` → ``3.8Gi``)."""

    total = parse_quantity(quantity)
    if total is None:
        return None
    for suffix, factor in _MEM_UNITS:
        if total >= factor:
            return f"{total / factor:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{int(total)}"


def percent(part: str | None, whole: str | None) -> str | None:
    """Render ``part``/``whole`` (two quantities) as a rounded percent (``47%``)."""

    numerator = parse_quantity(part)
    denominator = parse_quantity(whole)
    if numerator is None or denominator is None or denominator == 0:
        return None
    return f"{round(100 * numerator / denominator)}%"
