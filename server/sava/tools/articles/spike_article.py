import superdesk

from ..base import ToolContext, ToolResult, tool


@tool(
    name="spike_article",
    domain="articles",
    description="Spike (soft-delete) an article, removing it from the workflow. Reversible via unspike.",
    parameters={
        "type": "object",
        "properties": {"article_id": {"type": "string"}},
        "required": ["article_id"],
    },
    requires_confirmation=True,
    confirm_title="Spike this article? It will be removed from the workflow.",
    confirm_label="Spike",
)
async def spike_article(args, ctx: ToolContext) -> ToolResult:
    article_id = (args.get("article_id") or "").strip()
    if not article_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: article_id is required.")

    await superdesk.get_resource_service("archive_spike").patch_async(article_id, {})
    return ToolResult(
        ok=True,
        summary="Spiked article",
        for_model=f"Spiked article id={article_id}.",
        data={"article_id": article_id},
    )
