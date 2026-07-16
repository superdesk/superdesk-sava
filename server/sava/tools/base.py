"""SAVA tool framework: the Tool abstraction, execution context, result type,
and a registry that every tool self-registers into via the ``@tool`` decorator.

Add a new tool by dropping a module under ``tools/<domain>/`` that defines an
async handler decorated with ``@tool(...)``. The package auto-imports it, so it
shows up in the agent's toolset with no wiring.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolLink:
    """A client-navigable link. The client prepends its own origin + hash router,
    so the route stays host/port agnostic (no hardcoded URLs on the server)."""

    label: str
    route: str  # e.g. "/workspace/monitoring?item=<id>&action=edit"

    def to_dict(self) -> Dict[str, str]:
        return {"label": self.label, "route": self.route}


@dataclass
class ToolContext:
    """Everything a tool needs to act as the current user and build responses."""

    user: Optional[Dict[str, Any]] = None

    def link_to_item(
        self, item_id: str, action: str = "edit", label: str = "Open in monitoring"
    ) -> ToolLink:
        return ToolLink(label=label, route=f"/workspace/monitoring?item={item_id}&action={action}")


@dataclass
class ToolResult:
    """Outcome of a tool call.

    ``for_model`` is fed back to the LLM. ``summary``/``detail``/``links``/``data``
    are surfaced to the client UI (the activity log + link buttons).
    """

    ok: bool
    summary: str
    for_model: str
    detail: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    links: List[ToolLink] = field(default_factory=list)

    def action_dict(self, tool_name: str) -> Dict[str, Any]:
        return {
            "tool": tool_name,
            "ok": self.ok,
            "summary": self.summary,
            "detail": self.detail,
            "links": [link.to_dict() for link in self.links],
        }


ToolHandler = Callable[[Dict[str, Any], ToolContext], Awaitable[ToolResult]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: ToolHandler
    domain: str = "general"
    # If True, the agent loop pauses and asks the user to approve before running.
    requires_confirmation: bool = False
    confirm_title: Optional[str] = None
    confirm_label: str = "Confirm"


_REGISTRY: Dict[str, Tool] = {}


def tool(
    *,
    name: str,
    description: str,
    parameters: Dict[str, Any],
    domain: str = "general",
    requires_confirmation: bool = False,
    confirm_title: Optional[str] = None,
    confirm_label: str = "Confirm",
) -> Callable[[ToolHandler], ToolHandler]:
    """Register an async handler as a SAVA tool."""

    def decorator(fn: ToolHandler) -> ToolHandler:
        _REGISTRY[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=fn,
            domain=domain,
            requires_confirmation=requires_confirmation,
            confirm_title=confirm_title,
            confirm_label=confirm_label,
        )
        return fn

    return decorator


def get_tool(name: str) -> Optional[Tool]:
    return _REGISTRY.get(name)


def get_openai_tools() -> List[Dict[str, Any]]:
    """The tool schemas advertised to the model, OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in _REGISTRY.values()
    ]


async def run_tool(name: str, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
    """Execute a registered tool, turning any exception into a failed result so
    one bad call never crashes the whole request."""
    t = get_tool(name)
    if t is None:
        return ToolResult(
            ok=False,
            summary=f"Unknown tool: {name}",
            for_model=f"Error: unknown tool '{name}'.",
        )
    try:
        return await t.handler(args, ctx)
    except Exception as exc:  # noqa: BLE001 - surface any tool failure to the model
        logger.exception("SAVA tool '%s' failed", name)
        return ToolResult(
            ok=False,
            summary=f"{name} failed",
            detail=str(exc),
            for_model=f"Error running {name}: {exc}",
        )
