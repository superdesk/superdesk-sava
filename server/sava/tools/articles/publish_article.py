import superdesk

from ..base import ToolContext, ToolResult, tool


@tool(
    name="publish_article",
    domain="articles",
    description=(
        "Publish an existing article by id. This makes it public. The platform asks the "
        "user to confirm before it runs, so you do not need to ask yourself — just call it "
        "when the user wants to publish."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_id": {"type": "string", "description": "The id of the article to publish."},
        },
        "required": ["article_id"],
    },
    requires_confirmation=True,
    confirm_title="Publish this article? It will become public.",
    confirm_label="Publish",
)
async def publish_article(args, ctx: ToolContext) -> ToolResult:
    article_id = args.get("article_id")
    if not article_id:
        return ToolResult(
            ok=False,
            summary="No article id provided",
            for_model="Error: article_id is required to publish.",
        )

    await superdesk.get_resource_service("archive_publish").patch_async(article_id, {})
    return ToolResult(
        ok=True,
        summary="Published article",
        detail=f"id {article_id}",
        for_model=f"Published article id={article_id}.",
        data={"article_id": str(article_id)},
        links=[ctx.link_to_item(str(article_id), action="view")],
    )
