import superdesk

from ..base import ToolContext, ToolResult, tool
from ..lookups import planning_link


@tool(
    name="reschedule_planning_item",
    domain="planning",
    privilege="planning_planning_management",
    description=(
        "Reschedule a planning item, marking it as rescheduled. Its coverages are cancelled by "
        "this action. A reason may be required by the instance."
    ),
    parameters={
        "type": "object",
        "properties": {
            "planning_id": {"type": "string"},
            "reason": {"type": "string", "description": "Why the planning item is being rescheduled."},
        },
        "required": ["planning_id"],
    },
)
async def reschedule_planning_item(args, ctx: ToolContext) -> ToolResult:
    planning_id = (args.get("planning_id") or "").strip()
    if not planning_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: planning_id is required.")

    updates: dict = {}
    reason = (args.get("reason") or "").strip()
    if reason:
        updates["reason"] = reason

    await superdesk.get_resource_service("planning_reschedule").patch_async(planning_id, updates)
    return ToolResult(
        ok=True,
        summary="Rescheduled planning item",
        for_model=f"Rescheduled planning item id={planning_id}.",
        data={"planning_id": planning_id},
        links=[planning_link()],
    )
