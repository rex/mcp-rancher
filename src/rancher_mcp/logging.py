"""Logging configuration."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level_name: str) -> None:
    """Configure structured logging on stderr."""

    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)

    renderer: structlog.types.Processor
    if level <= logging.DEBUG:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            # Without this, `log.error(..., exc_info=True)` — used at four
            # call sites across this codebase (__main__.py, tools/support/
            # errors.py, tools/support/mutations.py, tools/pods_services/
            # shared.py) — leaves the RAW `exc_info=True` flag in the event
            # dict for the renderer below to serialize verbatim: a JSON log
            # line reading literally `"exc_info": true`, with the actual
            # exception type, message, and traceback silently discarded.
            # This renders the traceback into a real "exception" field
            # BEFORE either renderer runs, so every exc_info=True call
            # actually carries the failure it was logged to explain.
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
