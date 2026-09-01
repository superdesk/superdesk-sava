from typing import Any, Dict

import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool
from ..lookups import merge_extra_fields, protected_note, valid_iso_datetime


def _default_timezone() -> str:
    try:
        from superdesk.core import get_app_config

        return get_app_config("DEFAULT_TIMEZONE") or "UTC"
    except Exception:  # noqa: BLE001
        return "UTC"


@tool(
    name="create_event",
    domain="events",
    privilege="planning_event_management",
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
            "timezone": {
                "type": "string",
                "description": "IANA tz e.g. 'Europe/Prague'. Optional; instance default used if omitted.",
            },
            "slugline": {"type": "string"},
            "description_short": {"type": "string"},
            "location": {"type": "string", "description": "Free-text location name. Optional."},
            "fields": {
                "type": "object",
                "description": (
                    "Any other event fields this instance requires (see "
                    'describe_planning_profile \'event\'), e.g. {"language": "en"}.'
                ),
            },
        },
        "required": ["name", "start"],
    },
)
async def create_event(args, ctx: ToolContext) -> ToolResult:
    name = (args.get("name") or "").strip()
    start = (args.get("start") or "").strip()
    if not name or not start:
        return ToolResult(ok=False, summary="Missing input", for_model="An event needs a name and a start datetime.")
    if not valid_iso_datetime(start):
        return ToolResult(
            ok=False,
            summary="Invalid start",
            for_model=f"start '{start}' is not a valid ISO-8601 datetime (e.g. 2026-07-30T09:00:00).",
        )

    end = (args.get("end") or "").strip()
    if end and not valid_iso_datetime(end):
        return ToolResult(
            ok=False,
            summary="Invalid end",
            for_model=f"end '{end}' is not a valid ISO-8601 datetime (e.g. 2026-07-30T10:00:00).",
        )

    tz = (args.get("timezone") or "").strip() or _default_timezone()
    dates: Dict[str, Any] = {"start": start, "tz": tz}
    dates["end"] = end or start

    item: Dict[str, Any] = {"name": name, "dates": dates}
    if args.get("slugline"):
        item["slugline"] = args["slugline"]
    if args.get("description_short"):
        item["definition_short"] = args["description_short"]
    if args.get("location"):
        item["location"] = [{"name": args["location"]}]

    # Any instance-specific fields the model gathered from describe_planning_profile.
    dropped = merge_extra_fields(item, args.get("fields"))

    await superdesk.get_resource_service("events").post_async([item])
    event_id = str(item["_id"])
    return ToolResult(
        ok=True,
        summary=f"Created event “{name}”",
        detail=f"id {event_id}",
        for_model=f"Created event id={event_id} name='{name}' start={start} tz={tz}." + protected_note(dropped),
        data={"event_id": event_id, "name": name},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
