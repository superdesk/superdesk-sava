import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="postpone_planning_item",
    domain="planning",
    description="Postpone a planning item (and its coverages). A reason may be required by the instance.",
    parameters={
        "type": "object",
        "properties": {
            "planning_id": {"type": "string"},
            "reason": {"type": "string", "description": "Why the planning item is being postponed."},
        },
        "required": ["planning_id"],
    },
)
async def postpone_planning_item(args, ctx: ToolContext) -> ToolResult:
    planning_id = (args.get("planning_id") or "").strip()
    if not planning_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: planning_id is required.")

    from planning.planning.planning_postpone import process_postpone_planning_item

    service = superdesk.get_resource_service("planning")
    original = await service.find_one_async(req=None, _id=planning_id)
    if original is None:
        return ToolResult(
            ok=False, summary="Planning item not found", for_model=f"No planning item with id {planning_id}."
        )

    updates: dict = {}
    reason = (args.get("reason") or "").strip()
    if reason:
        updates["reason"] = reason

    await process_postpone_planning_item(updates, original)
    return ToolResult(
        ok=True,
        summary="Postponed planning item",
        for_model=f"Postponed planning item id={planning_id}.",
        data={"planning_id": planning_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
