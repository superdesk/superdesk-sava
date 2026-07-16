"""Shared, non-tool lookups used by multiple SAVA tools."""

from typing import Any, Dict, Optional, Tuple

import superdesk


async def resolve_desk_stage(
    desk_name: Optional[str], user: Optional[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], Any]:
    """Resolve a desk (and a stage on it) to place a new article on.

    Preference: named desk (exact, then case-insensitive) -> the user's own
    desk -> the first available desk.
    """
    desks_service = superdesk.get_resource_service("desks")
    desk: Optional[Dict[str, Any]] = None

    if desk_name:
        desk = await desks_service.find_one_async(req=None, name=desk_name)
        if desk is None:
            cursor = await desks_service.get_all_async()
            async for candidate in cursor:
                if (candidate.get("name") or "").lower() == desk_name.lower():
                    desk = candidate
                    break

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
