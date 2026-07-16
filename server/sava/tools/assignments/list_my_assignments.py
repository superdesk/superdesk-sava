import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="list_my_assignments",
    domain="assignments",
    description="List coverage assignments assigned to the current user.",
    parameters={
        "type": "object",
        "properties": {
            "state": {"type": "string", "description": "Optional assignment state filter, e.g. 'assigned', 'in_progress'."},
            "size": {"type": "integer", "description": "Max results (default 25)."},
        },
    },
)
async def list_my_assignments(args, ctx: ToolContext) -> ToolResult:
    if not ctx.user or not ctx.user.get("_id"):
        return ToolResult(ok=False, summary="No current user", for_model="Cannot determine the current user.")

    lookup = {"assigned_to.user": ctx.user["_id"]}
    if args.get("state"):
        lookup["assigned_to.state"] = args["state"]

    try:
        size = int(args.get("size") or 25)
    except (TypeError, ValueError):
        size = 25

    cursor = await superdesk.get_resource_service("assignments").get_from_mongo_async(req=None, lookup=lookup)
    items = []
    async for a in cursor:
        items.append(a)
        if len(items) >= size:
            break

    if not items:
        return ToolResult(ok=True, summary="No assignments", for_model="You have no assignments matching that.", data={"count": 0})

    lines = []
    for a in items:
        planning = a.get("planning") or {}
        assigned = a.get("assigned_to") or {}
        lines.append(
            f"- {planning.get('slugline') or '(coverage)'} — {assigned.get('state')} "
            f"({planning.get('g2_content_type')}) id={a.get('_id')}"
        )
    return ToolResult(
        ok=True,
        summary=f"You have {len(items)} assignment(s)",
        for_model=f"Your assignments ({len(items)}):\n" + "\n".join(lines),
        data={"count": len(items)},
        links=[ToolLink(label="Open assignments", route="/workspace/assignments")],
    )
