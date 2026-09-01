"""SAVA tool framework: the Tool abstraction, execution context, result type,
and a registry that every tool self-registers into via the ``@tool`` decorator.

Add a new tool by dropping a module under ``tools/<domain>/`` that defines an
async handler decorated with ``@tool(...)``. The package auto-imports it, so it
shows up in the agent's toolset with no wiring.
"""

import json
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
class ItemCard:
    """A Superdesk item the UI renders as a card (headline, state, desk, open link)
    instead of a text list. ``kind`` is article | event | planning | assignment."""

    kind: str
    id: str
    title: str
    route: str
    subtitle: Optional[str] = None
    state: Optional[str] = None
    desk: Optional[str] = None
    date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "title": self.title,
            "route": self.route,
            "subtitle": self.subtitle,
            "state": self.state,
            "desk": self.desk,
            "date": self.date,
        }


@dataclass
class ToolContext:
    """Everything a tool needs to act as the current user and build responses."""

    user: Optional[Dict[str, Any]] = None
    # Recorded as provenance on items the tools create or edit.
    model: Optional[str] = None
    conversation_id: Optional[str] = None

    def link_to_item(self, item_id: str, action: str = "edit", label: str = "Open in monitoring") -> ToolLink:
        return ToolLink(label=label, route=f"/workspace/monitoring?item={item_id}&action={action}")


@dataclass
class ToolResult:
    """Outcome of a tool call.

    ``for_model`` is fed back to the LLM. ``summary``/``detail``/``links``/``items``
    are surfaced to the client UI (the activity log, link buttons and item cards).
    """

    ok: bool
    summary: str
    for_model: str
    detail: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    links: List[ToolLink] = field(default_factory=list)
    items: List[ItemCard] = field(default_factory=list)

    def action_dict(self, tool_name: str) -> Dict[str, Any]:
        return {
            "tool": tool_name,
            "ok": self.ok,
            "summary": self.summary,
            "detail": self.detail,
            "links": [link.to_dict() for link in self.links],
            "items": [item.to_dict() for item in self.items],
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
    # Superdesk privilege the user must hold (e.g. "publish"). Tools call services
    # directly, bypassing the HTTP-layer privilege check, so every write tool must
    # declare the same privilege its REST resource requires.
    privilege: Optional[str] = None


_REGISTRY: Dict[str, Tool] = {}
_SCHEMA_CACHE: Optional[List[Dict[str, Any]]] = None


def tool(
    *,
    name: str,
    description: str,
    parameters: Dict[str, Any],
    domain: str = "general",
    requires_confirmation: bool = False,
    confirm_title: Optional[str] = None,
    confirm_label: str = "Confirm",
    privilege: Optional[str] = None,
) -> Callable[[ToolHandler], ToolHandler]:
    """Register an async handler as a SAVA tool."""

    def decorator(fn: ToolHandler) -> ToolHandler:
        global _SCHEMA_CACHE
        _SCHEMA_CACHE = None
        if name in _REGISTRY:
            logger.warning(
                "SAVA: tool name '%s' is already registered; %s is overriding it.",
                name,
                fn.__module__,
            )
        _REGISTRY[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=fn,
            domain=domain,
            requires_confirmation=requires_confirmation,
            confirm_title=confirm_title,
            confirm_label=confirm_label,
            privilege=privilege,
        )
        return fn

    return decorator


def get_tool(name: str) -> Optional[Tool]:
    return _REGISTRY.get(name)


def get_openai_tools() -> List[Dict[str, Any]]:
    """The tool schemas advertised to the model, OpenAI function-calling format.
    Built once per registry state (the registry is static after autoload) since
    it is sent on every model call."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = [
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
    return _SCHEMA_CACHE


def _coerce_json_args(args: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Repair args that a weaker model stringified.

    Small/local models often emit an ``array``/``object`` parameter as a JSON
    *string* (e.g. coverages='[{...}]') instead of the real structure. When the
    tool's schema declares the parameter as array/object but the value arrived as
    a string, parse it back so the handler receives what it expects.
    """
    props = (parameters or {}).get("properties") or {}
    for key, value in list(args.items()):
        if not isinstance(value, str):
            continue
        if (props.get(key) or {}).get("type") in ("array", "object"):
            try:
                args[key] = json.loads(value)
            except (TypeError, ValueError):
                pass  # leave it as-is; the handler still guards types
    return args


def _current_role() -> Optional[Dict[str, Any]]:
    """The role Superdesk resolved for this request, if we're inside one."""
    try:
        from quart import g

        return getattr(g, "role", None)
    except Exception:  # noqa: BLE001 - outside a request/app context
        return None


async def user_has_privilege(user: Dict[str, Any], privilege: str) -> bool:
    """Same resolution as Superdesk's own privilege rules: admins pass, otherwise
    the user's role privileges merged with their own must include ``privilege``."""
    from superdesk.users.async_service import get_privileges, is_admin

    if is_admin(user):
        return True
    role = _current_role()
    if role is None and user.get("role"):
        import superdesk

        role = await superdesk.get_resource_service("roles").find_one_async(req=None, _id=user["role"])
    return bool(get_privileges(user, role).get(privilege, False))


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
        # Mirror the HTTP layer: no user means a system/worker context and is allowed.
        if t.privilege and ctx.user is not None and not await user_has_privilege(ctx.user, t.privilege):
            return ToolResult(
                ok=False,
                summary="Not permitted",
                detail=f"requires the '{t.privilege}' privilege",
                for_model=(
                    f"Error: the user does not have the '{t.privilege}' privilege required "
                    f"to run {name}. Do not retry; tell the user."
                ),
            )
        args = _coerce_json_args(args, t.parameters)
        return await t.handler(args, ctx)
    except Exception as exc:  # noqa: BLE001 - surface any tool failure to the model
        logger.exception("SAVA tool '%s' failed", name)
        return ToolResult(
            ok=False,
            summary=f"{name} failed",
            detail=str(exc),
            for_model=f"Error running {name}: {exc}",
        )
