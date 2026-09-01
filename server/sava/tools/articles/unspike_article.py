import superdesk

from ..base import ToolContext, ToolResult, tool


@tool(
    name="unspike_article",
    domain="articles",
    privilege="unspike",
    description="Unspike a previously spiked article, restoring it to the workflow.",
    parameters={
        "type": "object",
        "properties": {"article_id": {"type": "string"}},
        "required": ["article_id"],
    },
)
async def unspike_article(args, ctx: ToolContext) -> ToolResult:
    article_id = (args.get("article_id") or "").strip()
    if not article_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: article_id is required.")

    await superdesk.get_resource_service("archive_unspike").patch_async(article_id, {})
    return ToolResult(
        ok=True,
        summary="Unspiked article",
        for_model=f"Unspiked article id={article_id}.",
        data={"article_id": article_id},
    )
