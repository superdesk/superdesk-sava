"""SAVA's tools: those of superdesk-tools, run as the signed-in user against this Superdesk's own API.

Every call goes over the API with the user's own session, so Superdesk applies their privileges, desk
membership and locks exactly as in its interface. A tool that needs the user's consent raises a question
instead of acting; SAVA shows it as an approval card and, on a yes, calls again with the token it came with.
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union
import aiohttp
from pydantic import BaseModel
from superdesk_tools.acting import Acting, Agent
from superdesk_tools.approval import Approvals
from superdesk_tools.calling import call, openai_tools
from superdesk_tools.catalog import ToolSpec, enabled_tools
from superdesk_tools.client import Credentials, SuperdeskClient
from superdesk_tools.errors import ConfirmationRequired, SuperdeskMCPError
from superdesk_tools.services import discovery
from superdesk_tools.settings import ToolSettings
from superdesk_tools.tools import ALL_TOOLSETS
from .default_settings import get_setting
from .results import ItemCard, Pending, ToolLink, ToolResult

logger = logging.getLogger(__name__)

AGENT = "sava"
MAX_CARDS = 25
PLANNING_ROUTE = "/planning"

# Per configuration: the enabled tools, their schemas, and the approvals that sign confirmation tokens
_CACHE: Dict[Tuple[str, bool, str], Tuple[ToolSettings, Dict[str, ToolSpec], List[Dict[str, Any]], Approvals]] = {}


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _configured() -> Tuple[ToolSettings, Dict[str, ToolSpec], List[Dict[str, Any]], Approvals]:
    key = (get_setting("SAVA_TOOLSETS"), _truthy(get_setting("SAVA_ALLOW_PUBLISH")), get_setting("SAVA_PROVENANCE_TAG"))
    if key not in _CACHE:
        settings = ToolSettings(toolsets=key[0], allow_publish=key[1], provenance_tag=key[2])
        specs = {spec.name: spec for spec in enabled_tools(ALL_TOOLSETS, settings, None)}
        _CACHE.clear()
        _CACHE[key] = (settings, specs, openai_tools(specs.values()), Approvals(settings))
    return _CACHE[key]


def schemas() -> List[Dict[str, Any]]:
    """The enabled tools in OpenAI function-calling format. Stable for a configuration, so prompt caches hold."""
    return _configured()[2]


def api_url() -> str:
    """This Superdesk's API, which the tools call as the user."""
    configured = get_setting("SAVA_SUPERDESK_API_URL")
    if configured:
        return configured
    try:
        from superdesk.core import get_app_config

        return str(get_app_config("SERVER_URL") or "http://localhost:5000/api")
    except Exception:  # noqa: BLE001 - outside an app context
        return "http://localhost:5000/api"


def _failed(name: str, message: str) -> ToolResult:
    return ToolResult(ok=False, summary=f"{name} failed", detail=message, for_model=f"Error: {message}")


class Toolbox:
    """The tools for one turn: signed in as the user, recording SAVA as the agent on what they change."""

    def __init__(self, client: Optional[SuperdeskClient], model: Optional[str], conversation_id: Optional[str]):
        self._client = client
        self._agent = Agent(name=AGENT, model=model, conversation=conversation_id)
        self._desk_names: Optional[Dict[str, str]] = None

    def schemas(self) -> List[Dict[str, Any]]:
        return schemas()

    async def run(
        self, name: str, args: Dict[str, Any], approved_question: Optional[str] = None
    ) -> Union[ToolResult, Pending]:
        """Run a tool. ``approved_question`` is the question the user said yes to, for this very call."""
        settings, specs, _, approvals = _configured()
        spec = specs.get(name)
        if spec is None:
            return _failed(name, f"There is no tool '{name}'")
        if self._client is None:
            return _failed(name, "SAVA has no Superdesk session to act with: sign in again")
        acting = Acting(self._client, settings, self._agent)
        try:
            try:
                result = await call(spec, acting, args, approvals=approvals)
            except ConfirmationRequired as asked:
                # The question is ours, written from the item as it is now: a different one means it changed
                if approved_question is None or asked.question != approved_question:
                    return Pending(question=asked.question)
                result = await call(spec, acting, args, approvals=approvals, confirm_token=asked.token)
        except SuperdeskMCPError as error:
            return _failed(name, str(error))
        except Exception as error:  # noqa: BLE001 - one bad call must not end the turn
            logger.exception("SAVA tool '%s' failed", name)
            return _failed(name, str(error) or type(error).__name__)
        return await self._shaped(name, result)

    async def _shaped(self, name: str, result: Any) -> ToolResult:
        data = result.model_dump(mode="json") if isinstance(result, BaseModel) else result
        if not isinstance(data, dict):
            data = {"result": data}
        warnings = [str(warning) for warning in data.get("warnings") or []]
        return ToolResult(
            ok=True,
            summary=str(data.get("summary") or _described(name, data)),
            detail="; ".join(warnings) or None,
            for_model=json.dumps(data, ensure_ascii=False, default=str),
            links=_links(data),
            items=await self._cards(data),
        )

    async def _desk(self, desk_id: Any) -> Optional[str]:
        if not desk_id or self._client is None:
            return None
        if self._desk_names is None:
            try:
                self._desk_names = {desk.id: desk.name for desk in (await discovery.list_desks(self._client)).desks}
            except Exception:  # noqa: BLE001 - a card without a desk name is still a card
                self._desk_names = {}
        return self._desk_names.get(str(desk_id))

    async def _cards(self, data: Dict[str, Any]) -> List[ItemCard]:
        cards: List[ItemCard] = []
        for item in _list(data, "items"):
            cards.append(
                ItemCard(
                    kind="article",
                    id=str(item.get("id")),
                    title=str(item.get("headline") or item.get("slugline") or item.get("id")),
                    route=_article_route(item.get("id")),
                    subtitle=item.get("slugline") if item.get("headline") else None,
                    state=item.get("state"),
                    desk=await self._desk(item.get("desk_id")),
                    date=item.get("updated"),
                )
            )
        for entry in _list(data, "entries") + ([data] if data.get("kind") in ("event", "planning") else []):
            cards.append(
                ItemCard(
                    kind=str(entry.get("kind")),
                    id=str(entry.get("id")),
                    title=str(entry.get("name") or entry.get("slugline") or entry.get("id")),
                    route=PLANNING_ROUTE,
                    subtitle=entry.get("slugline") if entry.get("name") else None,
                    state=entry.get("state"),
                    date=entry.get("starts"),
                )
            )
        for assignment in _list(data, "assignments"):
            cards.append(
                ItemCard(
                    kind="assignment",
                    id=str(assignment.get("id")),
                    title=str(assignment.get("slugline") or assignment.get("kind") or assignment.get("id")),
                    route="/workspace/assignments",
                    subtitle=assignment.get("kind"),
                    state=assignment.get("state"),
                    desk=await self._desk(assignment.get("desk_id")),
                    date=assignment.get("scheduled"),
                )
            )
        if "body_format" in data and data.get("id"):  # one article, read in full
            cards.append(
                ItemCard(
                    kind="article",
                    id=str(data["id"]),
                    title=str(data.get("headline") or data.get("slugline") or data["id"]),
                    route=_article_route(data["id"]),
                    state=data.get("state"),
                    desk=await self._desk(data.get("desk_id")),
                )
            )
        return cards[:MAX_CARDS]


def _list(data: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    return [entry for entry in data.get(key) or [] if isinstance(entry, dict)]


def _article_route(item_id: Any) -> str:
    return f"/workspace/monitoring?item={item_id}&action=edit"


def _links(data: Dict[str, Any]) -> List[ToolLink]:
    """A link to what a change was made to: articles open in monitoring, events and planning in planning."""
    if not (data.get("id") and data.get("action")):
        return []
    if "replaced_by" in data:  # a change to an event or a planning item
        return [ToolLink(label="Open planning", route=PLANNING_ROUTE)]
    return [ToolLink(label="Open in monitoring", route=_article_route(data["id"]))]


# How a list in a result is named in the activity log, where its key does not say it well
LIST_NAMES = {"entries": "events and planning items", "items": "items"}


def _described(name: str, data: Dict[str, Any]) -> str:
    """A line for the activity log when the result has no summary of its own: what was found, or who."""
    if name == "whoami" and (data.get("display_name") or data.get("username")):
        return f"Signed in as {data.get('display_name') or data.get('username')}"
    if not data.get("id"):  # a single item has lists of its own (calendars, coverages...): not what was found
        for key, value in data.items():
            if isinstance(value, list):
                return f"Found {len(value)} {LIST_NAMES.get(key, key.replace('_', ' '))}"
    return name.replace("_", " ").capitalize()


@asynccontextmanager
async def toolbox(
    token: Optional[str],
    *,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    model: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> AsyncIterator[Toolbox]:
    """The tools for one turn, signed in with the user's Superdesk session ``token``.

    ``session_id`` and ``user_id`` say whose session it is; without them, tools that need to know who acts
    (whoami, the user's own desks and items) cannot work, since a bare token does not tell.
    """
    if not token:
        yield Toolbox(None, model, conversation_id)
        return
    async with aiohttp.ClientSession() as session:
        credentials = Credentials(token=token, session_id=session_id)
        client = SuperdeskClient(session, api_url(), credentials, user_id=user_id)
        yield Toolbox(client, model, conversation_id)
