from datetime import timedelta

import superdesk
from superdesk.utc import utcnow

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="search_planning",
    domain="planning",
    description="Search/list planning items by slugline text and/or date (today, this_week, future).",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Text to match against the slugline."},
            "date_filter": {"type": "string", "enum": ["today", "this_week", "future"]},
            "size": {"type": "integer", "description": "Max results (default 25)."},
        },
    },
)
async def search_planning(args, ctx: ToolContext) -> ToolResult:
    conditions = [{"state": {"$ne": "spiked"}}]

    text = (args.get("query") or "").strip()
    if text:
        conditions.append({"slugline": {"$regex": text, "$options": "i"}})

    date_filter = (args.get("date_filter") or "").strip().lower()
    if date_filter:
        now = utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if date_filter == "today":
            conditions.append({"planning_date": {"$gte": start_of_day, "$lt": start_of_day + timedelta(days=1)}})
        elif date_filter == "this_week":
            conditions.append({"planning_date": {"$gte": start_of_day - timedelta(days=7)}})
        elif date_filter == "future":
            conditions.append({"planning_date": {"$gte": now}})

    lookup = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    try:
        size = int(args.get("size") or 25)
    except (TypeError, ValueError):
        size = 25

    cursor = await superdesk.get_resource_service("planning").get_from_mongo_async(req=None, lookup=lookup)
    items = []
    async for item in cursor:
        items.append(item)
        if len(items) >= size:
            break

    if not items:
        return ToolResult(ok=True, summary="No planning items found", for_model="No planning items matched.", data={"count": 0})

    lines = [
        f"- {i.get('slugline') or i.get('headline') or '(untitled)'} — {i.get('planning_date')} "
        f"(id={i.get('_id')}, coverages={len(i.get('coverages') or [])})"
        for i in items
    ]
    return ToolResult(
        ok=True,
        summary=f"Found {len(items)} planning item(s)",
        for_model=f"Found {len(items)} planning item(s):\n" + "\n".join(lines),
        data={"count": len(items)},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
