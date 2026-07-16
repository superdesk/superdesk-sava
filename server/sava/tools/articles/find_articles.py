from datetime import timedelta

from superdesk.utc import utcnow

from ..base import ToolContext, ToolResult, tool
from ..lookups import find_desk, find_user_by_name, format_article_results, run_article_search


def _date_range(date_filter: str):
    now = utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if date_filter == "today":
        return {"gte": start_of_day.isoformat()}
    if date_filter == "this_week":
        return {"gte": (start_of_day - timedelta(days=7)).isoformat()}
    if date_filter == "this_month":
        return {"gte": (start_of_day - timedelta(days=30)).isoformat()}
    return None


@tool(
    name="find_articles",
    domain="articles",
    description=(
        "Search working and published articles by any combination of filters. The "
        "workhorse for 'show me…' queries. Resolve a desk/author name first if needed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Free text (matches headline/slugline/body)."},
            "desk": {"type": "string", "description": "Desk name to filter by."},
            "author": {"type": "string", "description": "Author/creator name to filter by."},
            "states": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Workflow states, e.g. ['submitted','in_progress','published'].",
            },
            "type": {"type": "string", "description": "Item type, e.g. 'text', 'picture'."},
            "date_filter": {"type": "string", "enum": ["today", "this_week", "this_month"]},
            "date_field": {
                "type": "string",
                "enum": ["versioncreated", "firstcreated", "firstpublished"],
                "description": "Which date the filter applies to (default versioncreated).",
            },
            "size": {"type": "integer", "description": "Max results (default 25)."},
        },
    },
)
async def find_articles(args, ctx: ToolContext) -> ToolResult:
    must = []
    should = []

    query = (args.get("query") or "").strip()
    if query:
        must.append({"query_string": {"query": query}})

    desk_name = (args.get("desk") or "").strip()
    if desk_name:
        desk = await find_desk(desk_name)
        if desk is not None:
            must.append({"term": {"task.desk": str(desk["_id"])}})

    states = args.get("states")
    if isinstance(states, list) and states:
        must.append({"terms": {"state": states}})
    elif isinstance(states, str) and states:
        must.append({"term": {"state": states}})

    item_type = (args.get("type") or "").strip()
    if item_type:
        must.append({"term": {"type": item_type}})

    author = (args.get("author") or "").strip()
    if author:
        user = await find_user_by_name(author)
        if user is not None:
            should.append({"term": {"original_creator": str(user["_id"])}})
            should.append({"term": {"version_creator": str(user["_id"])}})
        should.append({"match": {"byline": author}})

    date_field = (args.get("date_field") or "versioncreated").strip()
    date_filter = (args.get("date_filter") or "").strip().lower()
    if date_filter:
        rng = _date_range(date_filter)
        if rng:
            must.append({"range": {date_field: rng}})

    try:
        size = int(args.get("size") or 25)
    except (TypeError, ValueError):
        size = 25

    items = await run_article_search(must=must, should=should, size=size)
    return format_article_results(items, ctx)
