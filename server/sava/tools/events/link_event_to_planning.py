import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="link_event_to_planning",
    domain="events",
    description="Link an event to an existing planning item (adds it to the planning item's related events).",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "planning_id": {"type": "string"},
            "link_type": {"type": "string", "enum": ["primary", "secondary"], "description": "Defaults to primary."},
        },
        "required": ["event_id", "planning_id"],
    },
)
async def link_event_to_planning(args, ctx: ToolContext) -> ToolResult:
    event_id = (args.get("event_id") or "").strip()
    planning_id = (args.get("planning_id") or "").strip()
    link_type = (args.get("link_type") or "primary").strip()
    if not event_id or not planning_id:
        return ToolResult(ok=False, summary="Missing input", for_model="event_id and planning_id are required.")

    events_service = superdesk.get_resource_service("events")
    planning_service = superdesk.get_resource_service("planning")

    event = await events_service.find_one_async(req=None, _id=event_id)
    if event is None:
        return ToolResult(ok=False, summary="Event not found", for_model=f"No event with id {event_id}.")
    plan = await planning_service.find_one_async(req=None, _id=planning_id)
    if plan is None:
        return ToolResult(ok=False, summary="Planning item not found", for_model=f"No planning item with id {planning_id}.")

    related = list(plan.get("related_events") or [])
    if any((r.get("_id") == event_id) for r in related):
        return ToolResult(
            ok=True,
            summary="Already linked",
            for_model=f"Event id={event_id} is already linked to planning item id={planning_id}.",
            data={"event_id": event_id, "planning_id": planning_id},
        )

    related.append({"_id": event_id, "link_type": link_type})
    await planning_service.patch_async(planning_id, {"related_events": related})
    return ToolResult(
        ok=True,
        summary="Linked event to planning item",
        for_model=f"Linked event id={event_id} to planning item id={planning_id} as {link_type}.",
        data={"event_id": event_id, "planning_id": planning_id},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
