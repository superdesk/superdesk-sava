"""Superdesk SAVA - natural language agent module."""

import logging

from .module import module  # noqa: F401

# Superdesk only raises its own namespaces (superdesk, apps, content_api) to INFO;
# the root stays at WARNING, so without this the per-turn "SAVA turn:" line
# (and any other INFO from this package) never reaches the console handler.
logging.getLogger(__name__).setLevel(logging.INFO)
