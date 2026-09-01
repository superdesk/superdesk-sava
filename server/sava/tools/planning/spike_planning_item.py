import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="spike_planning_item",
    domain="planning",
    privilege="planning_planning_spike",
    description="Spike (soft-delete) a planning item, removing it from the workflow. Reversible via unspike.",
    parameters={
        "type": "object",
        "properties": {"planning_id": {"type": "string"}},
        "required": ["planning_id"],
    },
    requires_confirmation=True,
    confirm_title="Spike this planning item? It will be removed from the workflow.",
    confirm_label="Spike",
)
async def spike_planning_item(args, ctx: ToolContext) -> ToolResult:
    planning_id = (args.get("planning_id") or "").strip()
    if not planning_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: planning_id is required.")

    from planning.planning.planning_spike import process_spike_planning_item

    service = superdesk.get_resource_service("planning")
    original = await service.find_one_async(req=None, _id=planning_id)
    if original is None:
        return ToolResult(
            ok=False, summary="Planning item not found", for_model=f"No planning item with id {planning_id}."
        )

    await process_spike_planning_item({}, original)
    return ToolResult(
        ok=True,
        summary="Spiked planning item",
        for_model=f"Spiked planning item id={planning_id}.",
        data={"planning_id": planning_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
