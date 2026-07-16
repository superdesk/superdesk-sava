import superdesk

from ..base import ToolContext, ToolResult, tool
from ..lookups import find_desk


@tool(
    name="move_article",
    domain="articles",
    description="Send/move an article to a desk (and optionally a specific stage).",
    parameters={
        "type": "object",
        "properties": {
            "article_id": {"type": "string"},
            "desk": {"type": "string", "description": "Target desk name."},
            "stage": {"type": "string", "description": "Target stage name. Optional; defaults to the desk's incoming stage."},
        },
        "required": ["article_id", "desk"],
    },
)
async def move_article(args, ctx: ToolContext) -> ToolResult:
    article_id = (args.get("article_id") or "").strip()
    desk_name = (args.get("desk") or "").strip()
    if not article_id or not desk_name:
        return ToolResult(ok=False, summary="Missing input", for_model="article_id and desk are required.")

    desk = await find_desk(desk_name)
    if desk is None:
        return ToolResult(ok=False, summary="Desk not found", for_model=f"No desk matched '{desk_name}'.")

    stage_id = None
    stage_name = (args.get("stage") or "").strip()
    if stage_name:
        cursor = await superdesk.get_resource_service("stages").get_async(req=None, lookup={"desk": desk["_id"]})
        async for s in cursor:
            if (s.get("name") or "").lower() == stage_name.lower():
                stage_id = s["_id"]
                break
    if stage_id is None:
        stage_id = desk.get("incoming_stage") or desk.get("working_stage")

    await superdesk.get_resource_service("move").move_content(
        article_id, {"task": {"desk": desk["_id"], "stage": stage_id}}
    )
    return ToolResult(
        ok=True,
        summary=f"Moved to {desk.get('name')}",
        for_model=f"Moved article id={article_id} to desk '{desk.get('name')}'.",
        data={"article_id": article_id},
        links=[ctx.link_to_item(article_id)],
    )
