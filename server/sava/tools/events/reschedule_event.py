from ..base import ToolContext, ToolLink, ToolResult, tool
from ._actions import lock_event, parse_dt


@tool(
    name="reschedule_event",
    domain="events",
    description=(
        "Reschedule an event to a new start/end date/time. Datetimes must be ISO 8601. "
        "Related coverages are cancelled by this action."
    ),
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "start": {"type": "string", "description": "New start, ISO 8601 (e.g. 2026-08-20T09:00:00)."},
            "end": {"type": "string", "description": "New end, ISO 8601."},
            "reason": {"type": "string", "description": "Why the event is being rescheduled."},
        },
        "required": ["event_id", "start", "end"],
    },
)
async def reschedule_event(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    start = (args.get("start") or "").strip()
    end = (args.get("end") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")
    if not start or not end:
        return ToolResult(ok=False, summary="Missing dates", for_model="Error: start and end are required.")

    from planning.events.events_reschedule import process_reschedule_event

    original = await lock_event(event_id, "reschedule")
    if original is None:
        return ToolResult(ok=False, summary="Event not found", for_model=f"No event with id {event_id}.")

    updates: dict = {"dates": {"start": parse_dt(start), "end": parse_dt(end)}}
    reason = (args.get("reason") or "").strip()
    if reason:
        updates["reason"] = reason

    await process_reschedule_event(updates, original)
    return ToolResult(
        ok=True,
        summary="Rescheduled event",
        for_model=f"Rescheduled event id={event_id} to {start} - {end}.",
        data={"event_id": event_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
