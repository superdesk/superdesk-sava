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
    name="search_planning",
    domain="planning",
    description="Search/list planning items by slugline text and/or date, soonest first.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Text to match against the slugline."},
            "date_filter": {"type": "string", "enum": DATE_FILTERS, "description": DATE_FILTER_DESCRIPTION},
            "size": {"type": "integer", "description": "Max results (default 25)."},
        },
    },
)
async def search_planning(args, ctx: ToolContext) -> ToolResult:
    conditions = [{"state": {"$ne": "spiked"}}]

    text = (args.get("query") or "").strip()
    if text:
        conditions.append({"slugline": contains(text)})

    date_filter = (args.get("date_filter") or "").strip().lower()
    window = mongo_date_filter(date_filter) if date_filter else None
    if window:
        conditions.append({"planning_date": window})

    lookup = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    size = parse_size(args)

    items = await mongo_find("planning", lookup, '[("planning_date", 1)]', size)

    if not items:
        return ToolResult(
            ok=True, summary="No planning items found", for_model="No planning items matched.", data={"count": 0}
        )

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
        links=[planning_link()],
    )
