"""Superdesk SAVA - natural language agent module."""

import logging
import sys

from .module import module  # noqa: F401

# Superdesk raises only its own namespaces to INFO and its console handler has no
# formatter, so left alone the per-turn "SAVA turn:" line is dropped (root is at
# WARNING) or printed bare. Give this package its own handler at INFO in the same
# layout as the server's request log: [timestamp] [pid] [LEVEL] message.
LOG_FORMAT = "[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S %z"


def _configure_logging() -> None:
    package_logger = logging.getLogger(__name__)
    if any(getattr(h, "_sava", False) for h in package_logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    handler._sava = True  # type: ignore[attr-defined]
    package_logger.addHandler(handler)
    package_logger.setLevel(logging.INFO)
    package_logger.propagate = False


_configure_logging()
