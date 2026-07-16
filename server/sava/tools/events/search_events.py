from datetime import timedelta

import superdesk
from superdesk.utc import utcnow

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="search_events",
    domain="events",
    description="Search/list calendar events by name/slugline text and/or date (today, this_week, future).",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Text to match against name/slugline."},
            "date_filter": {"type": "string", "enum": ["today", "this_week", "future"]},
            "size": {"type": "integer", "description": "Max results (default 25)."},
        },
    },
)
async def search_events(args, ctx: ToolContext) -> ToolResult:
    conditions = [{"state": {"$ne": "spiked"}}]

    text = (args.get("query") or "").strip()
    if text:
        conditions.append(
            {"$or": [{"name": {"$regex": text, "$options": "i"}}, {"slugline": {"$regex": text, "$options": "i"}}]}
        )

    date_filter = (args.get("date_filter") or "").strip().lower()
    if date_filter:
        now = utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if date_filter == "today":
            conditions.append({"dates.start": {"$gte": start_of_day, "$lt": start_of_day + timedelta(days=1)}})
        elif date_filter == "this_week":
            conditions.append({"dates.start": {"$gte": start_of_day, "$lt": start_of_day + timedelta(days=7)}})
        elif date_filter == "future":
            conditions.append({"dates.start": {"$gte": now}})

    lookup = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    try:
        size = int(args.get("size") or 25)
    except (TypeError, ValueError):
        size = 25

    cursor = await superdesk.get_resource_service("events").get_from_mongo_async(req=None, lookup=lookup)
    items = []
    async for item in cursor:
        items.append(item)
        if len(items) >= size:
            break

    if not items:
        return ToolResult(ok=True, summary="No events found", for_model="No events matched.", data={"count": 0})

    lines = [
        f"- {e.get('name') or e.get('slugline') or '(unnamed)'} — {(e.get('dates') or {}).get('start')} (id={e.get('_id')})"
        for e in items
    ]
    return ToolResult(
        ok=True,
        summary=f"Found {len(items)} event(s)",
        for_model=f"Found {len(items)} event(s):\n" + "\n".join(lines),
        data={"count": len(items)},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
