import superdesk

from ..base import ToolContext, ToolResult, tool


@tool(
    name="update_article",
    domain="articles",
    description=(
        "Edit an article's fields (headline, slugline, body_html, abstract, byline, "
        "ednote, priority, urgency, …). Pass only the fields to change."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_id": {"type": "string"},
            "fields": {
                "type": "object",
                "description": 'Fields to change, e.g. {"headline": "New headline", "body_html": "<p>...</p>"}.',
            },
        },
        "required": ["article_id", "fields"],
    },
)
async def update_article(args, ctx: ToolContext) -> ToolResult:
    article_id = (args.get("article_id") or "").strip()
    fields = args.get("fields")
    if not article_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: article_id is required.")
    if not isinstance(fields, dict) or not fields:
        return ToolResult(ok=False, summary="No fields", for_model="Provide a `fields` object of changes.")

    updates = {k: v for k, v in fields.items() if v is not None}
    await superdesk.get_resource_service("archive").patch_async(article_id, updates)

    changed = ", ".join(updates.keys())
    return ToolResult(
        ok=True,
        summary=f"Updated {changed}",
        for_model=f"Updated article id={article_id}; changed fields: {changed}.",
        data={"article_id": article_id},
        links=[ctx.link_to_item(article_id)],
    )
