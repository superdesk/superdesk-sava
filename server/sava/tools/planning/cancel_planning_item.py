import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="cancel_planning_item",
    domain="planning",
    description="Cancel a planning item (and its coverages). A reason may be required by the instance.",
    parameters={
        "type": "object",
        "properties": {
            "planning_id": {"type": "string"},
            "reason": {"type": "string", "description": "Why the planning item is being cancelled."},
        },
        "required": ["planning_id"],
    },
    requires_confirmation=True,
    confirm_title="Cancel this planning item? It and its coverages will be marked cancelled.",
    confirm_label="Cancel planning",
)
async def cancel_planning_item(args, ctx: ToolContext) -> ToolResult:
    planning_id = (args.get("planning_id") or "").strip()
    if not planning_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: planning_id is required.")

    updates: dict = {}
    reason = (args.get("reason") or "").strip()
    if reason:
        updates["reason"] = reason

    await superdesk.get_resource_service("planning_cancel").patch_async(planning_id, updates)
    return ToolResult(
        ok=True,
        summary="Cancelled planning item",
        for_model=f"Cancelled planning item id={planning_id}.",
        data={"planning_id": planning_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
