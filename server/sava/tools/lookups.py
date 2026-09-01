"""Shared, non-tool helpers used by multiple SAVA tools."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import superdesk
from eve.utils import ParsedRequest
from superdesk.core import json

from .base import ToolContext, ToolLink, ToolResult


def valid_iso_datetime(value: Any) -> bool:
    """True if ``value`` is a parseable ISO-8601 datetime string.

    Accepts a trailing 'Z' (Python 3.10's ``fromisoformat`` does not). Used to
    reject a model-hallucinated date with a clean error instead of a 500 from the
    resource layer.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if text[-1] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


# --- instance context --------------------------------------------------------


def instance_timezone() -> str:
    """The instance's configured timezone name (``DEFAULT_TIMEZONE``), or UTC."""
    try:
        from superdesk.core import get_app_config

        return get_app_config("DEFAULT_TIMEZONE") or "UTC"
    except Exception:  # noqa: BLE001 - outside an app context
        return "UTC"


def planning_link(label: str = "Open planning") -> ToolLink:
    return ToolLink(label=label, route="/planning")


# --- date filters ------------------------------------------------------------

DATE_FILTERS = ["today", "this_week", "this_month", "future"]

DATE_FILTER_DESCRIPTION = (
    "today = the current day; this_week = the current Monday-to-Sunday week; "
    "this_month = the current calendar month; future = from now onwards. "
    "Day boundaries follow the instance timezone. Same meaning in every search tool."
)


def date_window(date_filter: str, now: Optional[datetime] = None) -> Optional[Tuple[datetime, Optional[datetime]]]:
    """Half-open ``[start, end)`` UTC window for a ``date_filter`` value, with day
    boundaries computed in the instance timezone. ``end`` is None for open-ended
    windows. Returns None for an unknown filter.
    """
    try:
        tz = ZoneInfo(instance_timezone())
    except Exception:  # noqa: BLE001 - unknown zone name
        tz = ZoneInfo("UTC")
    now_utc = now or datetime.now(timezone.utc)
    local = now_utc.astimezone(tz)
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)

    if date_filter == "today":
        start, end = day, day + timedelta(days=1)
    elif date_filter == "this_week":
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=7)
    elif date_filter == "this_month":
        start = day.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    elif date_filter == "future":
        return now_utc, None
    else:
        return None
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def mongo_date_filter(date_filter: str) -> Optional[Dict[str, Any]]:
    window = date_window(date_filter)
    if window is None:
        return None
    start, end = window
    clause: Dict[str, Any] = {"$gte": start}
    if end is not None:
        clause["$lt"] = end
    return clause


def elastic_date_filter(date_filter: str) -> Optional[Dict[str, str]]:
    window = date_window(date_filter)
    if window is None:
        return None
    start, end = window
    clause = {"gte": start.isoformat()}
    if end is not None:
        clause["lt"] = end.isoformat()
    return clause


# --- model-input guards ------------------------------------------------------

MAX_RESULTS = 100

# Fields the model must never set directly: identity, versioning, workflow state,
# locking and ownership are owned by Superdesk. Anything starting with "_" is
# treated the same way.
PROTECTED_FIELDS = frozenset(
    {
        "guid",
        "type",
        "state",
        "pubstatus",
        "task",
        "lock_user",
        "lock_session",
        "lock_time",
        "lock_action",
        "original_creator",
        "version_creator",
        "firstcreated",
        "versioncreated",
        "firstpublished",
        "expiry",
        "expired",
        "unique_id",
        "unique_name",
        "family_id",
        "original_id",
        "item_id",
        "ingest_id",
        "ingest_provider",
        "recurrence_id",
    }
)


def parse_size(args: Dict[str, Any], default: int = 25, maximum: int = MAX_RESULTS) -> int:
    """Result-count argument from the model, defaulted and clamped to [1, maximum]."""
    try:
        size = int(args.get("size") or default)
    except (TypeError, ValueError):
        size = default
    return max(1, min(size, maximum))


def contains(text: str) -> Dict[str, str]:
    """Mongo case-insensitive substring match, with the (model-supplied) text
    escaped so regex metacharacters can't break or slow the query."""
    return {"$regex": re.escape(text), "$options": "i"}


def strip_protected_fields(fields: Any) -> Tuple[Dict[str, Any], List[str]]:
    """Split model-supplied field values into (allowed, dropped-protected-names).
    ``None`` values are dropped silently."""
    clean: Dict[str, Any] = {}
    dropped: List[str] = []
    if not isinstance(fields, dict):
        return clean, dropped
    for key, value in fields.items():
        if value is None:
            continue
        if not isinstance(key, str) or key.startswith("_") or key in PROTECTED_FIELDS:
            dropped.append(str(key))
        else:
            clean[key] = value
    return clean, dropped


def merge_extra_fields(item: Dict[str, Any], extra: Any) -> List[str]:
    """Merge a tool's free-form ``fields`` object into ``item`` without overriding
    keys the tool already set. Returns the protected field names it refused."""
    clean, dropped = strip_protected_fields(extra)
    for key, value in clean.items():
        if key not in item:
            item[key] = value
    return dropped


def protected_note(dropped: List[str]) -> str:
    """Suffix for ``for_model`` so the model learns which fields were refused."""
    return f" Ignored protected field(s): {', '.join(dropped)}." if dropped else ""


# --- desks / stages / users / profiles -------------------------------------


async def find_desk(name: str) -> Optional[Dict[str, Any]]:
    """Resolve a desk by name (exact, then case-insensitive). None if not found."""
    service = superdesk.get_resource_service("desks")
    desk = await service.find_one_async(req=None, name=name)
    if desk is None:
        cursor = await service.get_all_async()
        async for candidate in cursor:
            if (candidate.get("name") or "").lower() == name.lower():
                desk = candidate
                break
    return desk


async def resolve_desk_stage(
    desk_name: Optional[str], user: Optional[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], Any]:
    """Resolve a desk (and a stage on it) to place a new article on.

    Preference: named desk -> the user's own desk -> the first available desk.
    """
    desk: Optional[Dict[str, Any]] = None
    if desk_name:
        desk = await find_desk(desk_name)

    desks_service = superdesk.get_resource_service("desks")
    if desk is None and user and user.get("desk"):
        desk = await desks_service.find_one_async(req=None, _id=user["desk"])

    if desk is None:
        cursor = await desks_service.get_all_async()
        async for candidate in cursor:
            desk = candidate
            break

    if desk is None:
        return None, None

    return desk, desk.get("working_stage") or desk.get("incoming_stage")


async def find_user_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Resolve a user by display name / username / first / last (case-insensitive)."""
    service = superdesk.get_resource_service("users")
    match = contains(name)
    lookup = {"$or": [{f: match} for f in ("display_name", "username", "first_name", "last_name")]}
    cursor = await service.get_from_mongo_async(req=None, lookup=lookup)
    async for candidate in cursor:
        return candidate
    return None


async def get_content_profile(identifier: str) -> Optional[Dict[str, Any]]:
    """Find a content profile (content_types) by _id or case-insensitive label."""
    service = superdesk.get_resource_service("content_types")
    profile = await service.find_one_async(req=None, _id=identifier)
    if profile is None:
        cursor = await service.get_all_async()
        async for candidate in cursor:
            if (candidate.get("label") or "").lower() == identifier.lower():
                profile = candidate
                break
    return profile


async def get_planning_profile(name: str) -> Optional[Dict[str, Any]]:
    """Fetch a planning profile from ``planning_types`` by name.

    The name is one of 'event', 'planning', or 'coverage' (that is also the doc
    ``_id``). These profiles are configured per-instance and can change on the
    fly, so tools read them at runtime rather than assuming a fixed field set.
    """
    service = superdesk.get_resource_service("planning_types")
    profile = await service.find_one_async(req=None, _id=name)
    if profile is None:
        profile = await service.find_one_async(req=None, name=name)
    return profile


def split_required_optional(schema: Optional[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Split a profile ``schema`` dict into (required, optional) field-name lists.

    A field is required when its config is a dict with a truthy ``required`` key —
    the shape used by both content_types and planning_types.
    """
    required: List[str] = []
    optional: List[str] = []
    for field_name, cfg in (schema or {}).items():
        if cfg is None:
            continue
        if isinstance(cfg, dict) and cfg.get("required"):
            required.append(field_name)
        else:
            optional.append(field_name)
    return required, optional


# --- mongo search ----------------------------------------------------------


async def mongo_find(resource: str, lookup: Dict[str, Any], sort: str, size: int) -> List[Dict[str, Any]]:
    """Sorted, size-capped read straight from Mongo. ``sort`` uses Eve's literal
    form, e.g. ``'[("planning_date", 1)]'``."""
    req = ParsedRequest()
    req.sort = sort
    req.max_results = size
    cursor = await superdesk.get_resource_service(resource).get_from_mongo_async(req=req, lookup=lookup)
    items: List[Dict[str, Any]] = []
    async for item in cursor:
        items.append(item)
        if len(items) >= size:
            break
    return items


# --- article search --------------------------------------------------------


async def run_article_search(
    *,
    must: Optional[List[Dict[str, Any]]] = None,
    should: Optional[List[Dict[str, Any]]] = None,
    repo: str = "archive,published",
    size: int = 25,
    sort_field: str = "versioncreated",
) -> List[Dict[str, Any]]:
    """Run an article search via the federated `search` service.

    ``must``/``should`` are Elasticsearch clause lists. Visibility (private
    drafts, invisible stages) is enforced by the service for the current user.
    """
    bool_query: Dict[str, Any] = {}
    if must:
        bool_query["must"] = must
    if should:
        bool_query["should"] = should
        bool_query["minimum_should_match"] = 1
    if not bool_query:
        bool_query["must"] = [{"match_all": {}}]

    source = {
        "query": {"filtered": {"query": {"bool": bool_query}}},
        "size": size,
        "sort": [{sort_field: "desc"}],
    }

    req = ParsedRequest()
    req.args = {"source": json.dumps(source), "repo": repo}
    cursor = await superdesk.get_resource_service("search").get_async(req, None)
    return [doc async for doc in cursor]


def format_article_results(
    items: List[Dict[str, Any]], ctx: ToolContext, label: str = "article(s)", max_links: int = 6
) -> ToolResult:
    """Turn a list of found items into a ToolResult (summary lines + open links)."""
    lines: List[str] = []
    links: List[ToolLink] = []
    for item in items:
        headline = item.get("headline") or item.get("slugline") or "(untitled)"
        state = item.get("state") or "?"
        item_id = item.get("_id") or item.get("guid") or item.get("item_id")
        lines.append(f"- {headline} — {state} (id={item_id})")
        if len(links) < max_links and item_id:
            links.append(ctx.link_to_item(str(item_id), label=headline[:48]))

    if not items:
        return ToolResult(ok=True, summary=f"No {label} found", for_model=f"No matching {label}.", data={"count": 0})

    return ToolResult(
        ok=True,
        summary=f"Found {len(items)} {label}",
        for_model=f"Found {len(items)} {label}:\n" + "\n".join(lines),
        data={"count": len(items)},
        links=links,
    )
