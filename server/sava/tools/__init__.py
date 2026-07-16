"""SAVA tools package.

Auto-imports every tool module so each ``@tool`` decorator runs and the tool
self-registers. Re-exports the framework API the agent uses.
"""

import importlib
import pkgutil

from .base import (  # noqa: F401
    Tool,
    ToolContext,
    ToolResult,
    ToolLink,
    tool,
    get_tool,
    get_openai_tools,
    run_tool,
)


def _autoload() -> None:
    for module_info in pkgutil.walk_packages(__path__, __name__ + "."):
        importlib.import_module(module_info.name)


_autoload()
