from typing import Any, Dict

import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


def _default_timezone() -> str:
    try:
        from superdesk.core import get_app_config

        return get_app_config("DEFAULT_TIMEZONE") or "UTC"
    except Exception:  # noqa: BLE001
        return "UTC"


@tool(
    name="create_event",
    domain="events",
    description=(
        "Create a calendar event. Requires a name and an ISO start datetime. Use the "
        "current date/time from your context to compute relative dates (e.g. 'Friday 9am')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "start": {"type": "string", "description": "ISO datetime for the event start."},
            "end": {"type": "string", "description": "ISO datetime for the event end. Optional."},
            "timezone": {"type": "string", "description": "IANA tz e.g. 'Europe/Prague'. Optional; instance default used if omitted."},
            "slugline": {"type": "string"},
            "description_short": {"type": "string"},
            "location": {"type": "string", "description": "Free-text location name. Optional."},
        },
        "required": ["name", "start"],
    },
)
async def create_event(args, ctx: ToolContext) -> ToolResult:
    name = (args.get("name") or "").strip()
    start = (args.get("start") or "").strip()
    if not name or not start:
        return ToolResult(ok=False, summary="Missing input", for_model="An event needs a name and a start datetime.")

    tz = (args.get("timezone") or "").strip() or _default_timezone()
    dates: Dict[str, Any] = {"start": start, "tz": tz}
    end = (args.get("end") or "").strip()
    dates["end"] = end or start

    item: Dict[str, Any] = {"name": name, "dates": dates}
    if args.get("slugline"):
        item["slugline"] = args["slugline"]
    if args.get("description_short"):
        item["definition_short"] = args["description_short"]
    if args.get("location"):
        item["location"] = [{"name": args["location"]}]

    await superdesk.get_resource_service("events").post_async([item])
    event_id = str(item["_id"])
    return ToolResult(
        ok=True,
        summary=f"Created event “{name}”",
        detail=f"id {event_id}",
        for_model=f"Created event id={event_id} name='{name}' start={start} tz={tz}.",
        data={"event_id": event_id, "name": name},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
