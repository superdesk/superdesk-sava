from typing import Any, Dict

import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="update_event",
    domain="events",
    description="Update an event's name, slugline, description, or dates (start/end/timezone).",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "name": {"type": "string"},
            "slugline": {"type": "string"},
            "description_short": {"type": "string"},
            "start": {"type": "string", "description": "New ISO start datetime."},
            "end": {"type": "string", "description": "New ISO end datetime."},
            "timezone": {"type": "string"},
        },
        "required": ["event_id"],
    },
)
async def update_event(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: event_id is required.")

    service = superdesk.get_resource_service("events")
    event = await service.find_one_async(req=None, _id=event_id)
    if event is None:
        return ToolResult(ok=False, summary="Event not found", for_model=f"No event with id {event_id}.")

    updates: Dict[str, Any] = {}
    if args.get("name"):
        updates["name"] = args["name"]
    if args.get("slugline"):
        updates["slugline"] = args["slugline"]
    if args.get("description_short"):
        updates["definition_short"] = args["description_short"]

    if args.get("start") or args.get("end") or args.get("timezone"):
        dates = dict(event.get("dates") or {})
        if args.get("start"):
            dates["start"] = args["start"]
        if args.get("end"):
            dates["end"] = args["end"]
        if args.get("timezone"):
            dates["tz"] = args["timezone"]
        updates["dates"] = dates

    if not updates:
        return ToolResult(ok=False, summary="Nothing to update", for_model="No changed fields were provided.")

    await service.patch_async(event_id, updates)
    return ToolResult(
        ok=True,
        summary=f"Updated event ({', '.join(updates.keys())})",
        for_model=f"Updated event id={event_id}; changed: {', '.join(updates.keys())}.",
        data={"event_id": event_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
