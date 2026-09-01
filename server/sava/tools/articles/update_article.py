import superdesk

from ..base import ToolContext, ToolResult, tool
from ..lookups import protected_note, strip_protected_fields
from ..provenance import stamp_update


@tool(
    name="update_article",
    domain="articles",
    privilege="archive",
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

    updates, dropped = strip_protected_fields(fields)
    if not updates:
        return ToolResult(
            ok=False,
            summary="No editable fields",
            for_model="None of the given fields can be edited directly." + protected_note(dropped),
        )
    service = superdesk.get_resource_service("archive")
    original = await service.find_one_async(req=None, _id=article_id)
    if original is None:
        return ToolResult(ok=False, summary="Not found", for_model=f"No article found with id {article_id}.")
    stamp_update(updates, original, ctx, "update_article")
    await service.patch_async(article_id, updates)

    changed = ", ".join(k for k in updates if k not in ("extra", "subject") or k in fields)
    return ToolResult(
        ok=True,
        summary=f"Updated {changed}",
        for_model=f"Updated article id={article_id}; changed fields: {changed}." + protected_note(dropped),
        data={"article_id": article_id},
        links=[ctx.link_to_item(article_id)],
    )
