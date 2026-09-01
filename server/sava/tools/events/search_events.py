from typing import Any, Dict, List

from ..base import ToolContext, ToolResult, tool
from ..lookups import (
    DATE_FILTERS,
    DATE_FILTER_DESCRIPTION,
    contains,
    mongo_date_filter,
    mongo_find,
    parse_size,
    planning_link,
)


@tool(
    name="search_events",
    domain="events",
    description="Search/list calendar events by name/slugline text and/or date, soonest first.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Text to match against name/slugline."},
            "date_filter": {"type": "string", "enum": DATE_FILTERS, "description": DATE_FILTER_DESCRIPTION},
            "size": {"type": "integer", "description": "Max results (default 25)."},
        },
    },
)
async def search_events(args, ctx: ToolContext) -> ToolResult:
    conditions: List[Dict[str, Any]] = [{"state": {"$ne": "spiked"}}]

    text = (args.get("query") or "").strip()
    if text:
        conditions.append({"$or": [{"name": contains(text)}, {"slugline": contains(text)}]})

    date_filter = (args.get("date_filter") or "").strip().lower()
    window = mongo_date_filter(date_filter) if date_filter else None
    if window:
        conditions.append({"dates.start": window})

    lookup = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    size = parse_size(args)

    items = await mongo_find("events", lookup, '[("dates.start", 1)]', size)

    if not items:
        return ToolResult(ok=True, summary="No events found", for_model="No events matched.", data={"count": 0})

    lines = [
        f"- {e.get('name') or e.get('slugline') or '(unnamed)'} — "
        f"{(e.get('dates') or {}).get('start')} (id={e.get('_id')})"
        for e in items
    ]
    return ToolResult(
        ok=True,
        summary=f"Found {len(items)} event(s)",
        for_model=f"Found {len(items)} event(s):\n" + "\n".join(lines),
        data={"count": len(items)},
        links=[planning_link()],
    )
