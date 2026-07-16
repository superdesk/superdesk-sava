"""SAVA configuration.

Fallback defaults live here. Override any of them via an environment variable
of the same name (typically set in the Superdesk server ``.env`` file). A client
that wants a different model only needs to set ``SAVA_MODEL``.
"""

import os

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


# --- Resolution --------------------------------------------------------------

_DEFAULTS = {
    "SAVA_OPENROUTER_API_KEY": SAVA_OPENROUTER_API_KEY,
    "SAVA_MODEL": SAVA_MODEL,
    "SAVA_OPENROUTER_BASE_URL": SAVA_OPENROUTER_BASE_URL,
    "SAVA_MAX_STEPS": SAVA_MAX_STEPS,
    "SAVA_MAX_HISTORY_MESSAGES": SAVA_MAX_HISTORY_MESSAGES,
}


def get_setting(name: str) -> str:
    """Resolve a ``SAVA_*`` setting: environment first, then the fallback default."""
    return os.environ.get(name, str(_DEFAULTS.get(name, "")))


def get_int_setting(name: str, minimum: int = 1) -> int:
    """Resolve an integer ``SAVA_*`` setting, guarding against bad values."""
    try:
        return max(minimum, int(get_setting(name)))
    except (TypeError, ValueError):
        return max(minimum, int(_DEFAULTS.get(name, minimum)))
