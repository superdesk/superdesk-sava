import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="post_event",
    domain="events",
    description="Post (publish) an event so it appears in the public calendar. Requires user confirmation.",
    parameters={
        "type": "object",
        "properties": {"event_id": {"type": "string"}},
        "required": ["event_id"],
    },
    requires_confirmation=True,
    confirm_title="Post this event? It will be published to the calendar.",
    confirm_label="Post",
)
async def post_event(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")

    await superdesk.get_resource_service("events_post").create_async(
        [{"event": event_id, "pubstatus": "usable"}]
    )
    return ToolResult(
        ok=True,
        summary="Posted event",
        detail=f"id {event_id}",
        for_model=f"Posted event id={event_id} (pubstatus=usable).",
        data={"event_id": event_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
