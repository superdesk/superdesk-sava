import superdesk

from ..base import ToolContext, ToolResult, tool
from ..lookups import planning_link


@tool(
    name="unspike_planning_item",
    domain="planning",
    privilege="planning_planning_unspike",
    description="Unspike a previously spiked planning item, restoring it to the workflow.",
    parameters={
        "type": "object",
        "properties": {"planning_id": {"type": "string"}},
        "required": ["planning_id"],
    },
)
async def unspike_planning_item(args, ctx: ToolContext) -> ToolResult:
    planning_id = (args.get("planning_id") or "").strip()
    if not planning_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: planning_id is required.")

    from planning.planning.planning_spike import process_unspike_planning_item

    service = superdesk.get_resource_service("planning")
    original = await service.find_one_async(req=None, _id=planning_id)
    if original is None:
        return ToolResult(
            ok=False, summary="Planning item not found", for_model=f"No planning item with id {planning_id}."
        )

    await process_unspike_planning_item({}, original)
    return ToolResult(
        ok=True,
        summary="Unspiked planning item",
        for_model=f"Unspiked planning item id={planning_id}.",
        data={"planning_id": planning_id},
        links=[planning_link()],
    )
