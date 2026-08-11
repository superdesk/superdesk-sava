from ..base import ToolContext, ToolLink, ToolResult, tool
from ._actions import lock_event


@tool(
    name="cancel_event",
    domain="events",
    description=(
        "Cancel an event, marking it and its related planning as cancelled. "
        "A reason may be required by the instance."
    ),
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "reason": {"type": "string", "description": "Why the event is being cancelled."},
        },
        "required": ["event_id"],
    },
    requires_confirmation=True,
    confirm_title="Cancel this event? It and its related planning will be marked cancelled.",
    confirm_label="Cancel event",
)
async def cancel_event(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")

    from planning.events.events_cancel import process_cancel_event

    original = await lock_event(event_id, "cancel")
    if original is None:
        return ToolResult(ok=False, summary="Event not found", for_model=f"No event with id {event_id}.")

    updates: dict = {}
    reason = (args.get("reason") or "").strip()
    if reason:
        updates["reason"] = reason

    await process_cancel_event(updates, original)
    return ToolResult(
        ok=True,
        summary="Cancelled event",
        for_model=f"Cancelled event id={event_id}.",
        data={"event_id": event_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
