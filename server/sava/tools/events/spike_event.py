import superdesk

from ..base import ToolContext, ToolResult, tool
from ..lookups import planning_link


@tool(
    name="spike_event",
    domain="events",
    privilege="planning_event_spike",
    description="Spike (soft-delete) an event, removing it from the workflow. Reversible via unspike.",
    parameters={
        "type": "object",
        "properties": {"event_id": {"type": "string"}},
        "required": ["event_id"],
    },
    requires_confirmation=True,
    confirm_title="Spike this event? It will be removed from the workflow.",
    confirm_label="Spike",
)
async def spike_event(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")

    from planning.events.events_spike import process_spike_event

    service = superdesk.get_resource_service("events")
    original = await service.find_one_async(req=None, _id=event_id)
    if original is None:
        return ToolResult(ok=False, summary="Event not found", for_model=f"No event with id {event_id}.")

    await process_spike_event({}, original)
    return ToolResult(
        ok=True,
        summary="Spiked event",
        for_model=f"Spiked event id={event_id}.",
        data={"event_id": event_id},
        links=[planning_link()],
    )
