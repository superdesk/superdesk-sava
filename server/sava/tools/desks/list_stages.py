import superdesk

from ..base import ToolContext, ToolResult, tool
from ..lookups import find_desk


@tool(
    name="list_stages",
    domain="desks",
    description="List the stages of a desk (e.g. Incoming, Working, Output). Use to resolve a stage name to an id.",
    parameters={
        "type": "object",
        "properties": {
            "desk": {"type": "string", "description": "Desk name whose stages to list."},
        },
        "required": ["desk"],
    },
)
async def list_stages(args, ctx: ToolContext) -> ToolResult:
    desk = await find_desk((args.get("desk") or "").strip())
    if desk is None:
        return ToolResult(
            ok=False,
            summary="Desk not found",
            for_model=f"No desk matched '{args.get('desk')}'.",
        )

    cursor = await superdesk.get_resource_service("stages").get_async(
        req=None, lookup={"desk": desk["_id"]}
    )
    stages = [{"id": str(s.get("_id")), "name": s.get("name")} async for s in cursor]
    listing = ", ".join(f"{s['name']} (id={s['id']})" for s in stages) or "(none)"
    return ToolResult(
        ok=True,
        summary=f"{len(stages)} stage(s) on {desk.get('name')}",
        detail=listing,
        for_model=f"Stages on desk '{desk.get('name')}': {listing}",
        data={"stages": stages},
    )
