import superdesk

from ..base import ToolContext, ToolResult, tool
from ..lookups import planning_link


@tool(
    name="unpost_planning_item",
    domain="planning",
    privilege="planning_planning_unpost",
    description="Unpost a posted planning item, withdrawing it from publication (sets pubstatus to cancelled).",
    parameters={
        "type": "object",
        "properties": {"planning_id": {"type": "string"}},
        "required": ["planning_id"],
    },
    requires_confirmation=True,
    confirm_title="Unpost this planning item? It will be withdrawn from publication.",
    confirm_label="Unpost",
)
async def unpost_planning_item(args, ctx: ToolContext) -> ToolResult:
    planning_id = (args.get("planning_id") or "").strip()
    if not planning_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: planning_id is required.")

    await superdesk.get_resource_service("planning_post").create_async(
        [{"planning": planning_id, "pubstatus": "cancelled"}]
    )
    return ToolResult(
        ok=True,
        summary="Unposted planning item",
        for_model=f"Unposted planning item id={planning_id} (pubstatus=cancelled).",
        data={"planning_id": planning_id},
        links=[planning_link()],
    )
