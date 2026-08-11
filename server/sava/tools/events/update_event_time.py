from ..base import ToolContext, ToolLink, ToolResult, tool
from ._actions import lock_event, parse_dt


@tool(
    name="update_event_time",
    domain="events",
    description="Change an event's start/end date/time without rescheduling. Datetimes must be ISO 8601.",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "start": {"type": "string", "description": "New start, ISO 8601 (e.g. 2026-08-20T09:00:00)."},
            "end": {"type": "string", "description": "New end, ISO 8601."},
        },
        "required": ["event_id", "start", "end"],
    },
)
async def update_event_time(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    start = (args.get("start") or "").strip()
    end = (args.get("end") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")
    if not start or not end:
        return ToolResult(ok=False, summary="Missing dates", for_model="Error: start and end are required.")

    from planning.events.events_update_time import process_update_time

    original = await lock_event(event_id, "update_time")
    if original is None:
        return ToolResult(ok=False, summary="Event not found", for_model=f"No event with id {event_id}.")

    updates: dict = {"dates": {"start": parse_dt(start), "end": parse_dt(end)}}

    await process_update_time(updates, original)
    return ToolResult(
        ok=True,
        summary="Updated event time",
        for_model=f"Updated event id={event_id} time to {start} - {end}.",
        data={"event_id": event_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
