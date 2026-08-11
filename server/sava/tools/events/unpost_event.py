import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="unpost_event",
    domain="events",
    description="Unpost a posted event, withdrawing it from the public calendar (sets pubstatus to cancelled).",
    parameters={
        "type": "object",
        "properties": {"event_id": {"type": "string"}},
        "required": ["event_id"],
    },
    requires_confirmation=True,
    confirm_title="Unpost this event? It will be withdrawn from the public calendar.",
    confirm_label="Unpost",
)
async def unpost_event(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")

    await superdesk.get_resource_service("events_post").create_async([{"event": event_id, "pubstatus": "cancelled"}])
    return ToolResult(
        ok=True,
        summary="Unposted event",
        for_model=f"Unposted event id={event_id} (pubstatus=cancelled).",
        data={"event_id": event_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
