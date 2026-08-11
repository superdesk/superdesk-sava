import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="unspike_event",
    domain="events",
    description="Unspike a previously spiked event, restoring it to the workflow.",
    parameters={
        "type": "object",
        "properties": {"event_id": {"type": "string"}},
        "required": ["event_id"],
    },
)
async def unspike_event(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")

    from planning.events.events_spike import process_unspike_event

    service = superdesk.get_resource_service("events")
    original = await service.find_one_async(req=None, _id=event_id)
    if original is None:
        return ToolResult(ok=False, summary="Event not found", for_model=f"No event with id {event_id}.")

    await process_unspike_event({}, original)
    return ToolResult(
        ok=True,
        summary="Unspiked event",
        for_model=f"Unspiked event id={event_id}.",
        data={"event_id": event_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
