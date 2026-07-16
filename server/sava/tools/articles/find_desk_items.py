from ..base import ToolContext, ToolResult, tool
from ..lookups import find_desk, format_article_results, run_article_search


@tool(
    name="find_desk_items",
    domain="articles",
    description="List the working items currently on a desk (optionally filtered by state).",
    parameters={
        "type": "object",
        "properties": {
            "desk": {"type": "string", "description": "Desk name."},
            "states": {"type": "array", "items": {"type": "string"}, "description": "Optional states filter."},
            "size": {"type": "integer", "description": "Max results (default 25)."},
        },
        "required": ["desk"],
    },
)
async def find_desk_items(args, ctx: ToolContext) -> ToolResult:
    desk_name = (args.get("desk") or "").strip()
    if not desk_name:
        return ToolResult(ok=False, summary="No desk", for_model="A desk name is required.")

    desk = await find_desk(desk_name)
    if desk is None:
        return ToolResult(ok=False, summary="Desk not found", for_model=f"No desk matched '{desk_name}'.")

    must = [{"term": {"task.desk": str(desk["_id"])}}]
    states = args.get("states")
    if isinstance(states, list) and states:
        must.append({"terms": {"state": states}})

    try:
        size = int(args.get("size") or 25)
    except (TypeError, ValueError):
        size = 25

    items = await run_article_search(must=must, repo="archive", size=size)
    return format_article_results(items, ctx, label=f"item(s) on {desk.get('name')}")
