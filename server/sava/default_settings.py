"""SAVA configuration.

Fallback defaults live here. Override any of them via an environment variable
of the same name (typically set in the Superdesk server ``.env`` file) or by
defining it in the Superdesk ``settings.py``. Environment wins over settings.py,
which wins over the defaults here. A client that wants a different model only
needs to set ``SAVA_MODEL``.
"""

import os
from typing import Optional

# --- Fallback defaults -------------------------------------------------------

# OpenRouter API key. Required for SAVA to work. No default for obvious reasons.
SAVA_OPENROUTER_API_KEY = ""

# Default model. Superdesk is open source, so we default to an open model.
SAVA_MODEL = "openai/gpt-oss-120b"

# OpenRouter is OpenAI-API-compatible; this is its base URL.
SAVA_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Max agent loop iterations (model call -> tool calls -> model call ...).
SAVA_MAX_STEPS = 6

# Max number of prior conversation messages to keep when a client sends history
# back. Bounds token growth over a long chat. Trimmed at a user-message boundary
# so tool-call/tool-result pairs are never split.
SAVA_MAX_HISTORY_MESSAGES = 20


# Visible provenance tag. When set (e.g. "AI-assisted"), items SAVA creates or
# edits also get a `subject` entry with that name so they can be seen and
# filtered in monitoring; the structured record under `extra.sava` is always
# written. Create a vocabulary with the scheme's id to make the tag filterable.
SAVA_PROVENANCE_TAG = ""
SAVA_PROVENANCE_SCHEME = "sava"


# --- Resolution --------------------------------------------------------------

_DEFAULTS = {
    "SAVA_OPENROUTER_API_KEY": SAVA_OPENROUTER_API_KEY,
    "SAVA_MODEL": SAVA_MODEL,
    "SAVA_OPENROUTER_BASE_URL": SAVA_OPENROUTER_BASE_URL,
    "SAVA_MAX_STEPS": SAVA_MAX_STEPS,
    "SAVA_MAX_HISTORY_MESSAGES": SAVA_MAX_HISTORY_MESSAGES,
    "SAVA_PROVENANCE_TAG": SAVA_PROVENANCE_TAG,
    "SAVA_PROVENANCE_SCHEME": SAVA_PROVENANCE_SCHEME,
}


def _app_config(name: str) -> Optional[str]:
    """The value from the running Superdesk app's config (settings.py), if any."""
    try:
        from superdesk.core import get_app_config

        value = get_app_config(name)
    except Exception:  # noqa: BLE001 - no app context (tests, tooling)
        return None
    return None if value is None else str(value)


def get_setting(name: str) -> str:
    """Resolve a ``SAVA_*`` setting: environment, then Superdesk app config, then
    the fallback default."""
    value = os.environ.get(name)
    if value is None:
        value = _app_config(name)
    if value is None:
        value = str(_DEFAULTS.get(name, ""))
    return value


def get_int_setting(name: str, minimum: int = 1) -> int:
    """Resolve an integer ``SAVA_*`` setting, guarding against bad values."""
    try:
        return max(minimum, int(get_setting(name)))
    except (TypeError, ValueError):
        return max(minimum, int(str(_DEFAULTS.get(name, minimum))))
