from ..base import ToolContext, ToolResult, tool
from ..lookups import format_article_results, run_article_search


@tool(
    name="find_my_articles",
    domain="articles",
    description="List articles authored or created by the current user (your items / drafts).",
    parameters={
        "type": "object",
        "properties": {
            "states": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional states filter, e.g. ['draft'] for drafts only.",
            },
            "size": {"type": "integer", "description": "Max results (default 25)."},
        },
    },
)
async def find_my_articles(args, ctx: ToolContext) -> ToolResult:
    if not ctx.user or not ctx.user.get("_id"):
        return ToolResult(
            ok=False,
            summary="No current user",
            for_model="Cannot determine the current user, so 'my articles' can't be resolved.",
        )

    uid = str(ctx.user["_id"])
    must = [
        {
            "bool": {
                "should": [
                    {"term": {"original_creator": uid}},
                    {"term": {"version_creator": uid}},
                ],
                "minimum_should_match": 1,
            }
        }
    ]

    states = args.get("states")
    if isinstance(states, list) and states:
        must.append({"terms": {"state": states}})

    try:
        size = int(args.get("size") or 25)
    except (TypeError, ValueError):
        size = 25

    items = await run_article_search(must=must, size=size)
    return format_article_results(items, ctx, label="article(s) by you")
