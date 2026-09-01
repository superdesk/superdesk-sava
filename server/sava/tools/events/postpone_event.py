from ..base import ToolContext, ToolLink, ToolResult, tool
from ._actions import run_event_action


@tool(
    name="postpone_event",
    domain="events",
    privilege="planning_event_management",
    description="Postpone an event, marking it and its related planning as postponed.",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "reason": {"type": "string", "description": "Why the event is being postponed."},
        },
        "required": ["event_id"],
    },
)
async def postpone_event(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")

    from planning.events.events_postpone import process_postpone_event

    updates: dict = {}
    reason = (args.get("reason") or "").strip()
    if reason:
        updates["reason"] = reason

    if await run_event_action(event_id, "postpone", process_postpone_event, updates) is None:
        return ToolResult(ok=False, summary="Event not found", for_model=f"No event with id {event_id}.")
    return ToolResult(
        ok=True,
        summary="Postponed event",
        for_model=f"Postponed event id={event_id}.",
        data={"event_id": event_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
