"""Shared, non-tool helpers used by multiple SAVA tools."""

from typing import Any, Dict, List, Optional, Tuple

import superdesk
from eve.utils import ParsedRequest
from superdesk.core import json

from .base import ToolContext, ToolResult


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
    lookup = {
        "$or": [
            {"display_name": {"$regex": name, "$options": "i"}},
            {"username": {"$regex": name, "$options": "i"}},
            {"first_name": {"$regex": name, "$options": "i"}},
            {"last_name": {"$regex": name, "$options": "i"}},
        ]
    }
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
    links = []
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
