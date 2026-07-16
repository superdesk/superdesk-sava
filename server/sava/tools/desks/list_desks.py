import superdesk

from ..base import ToolContext, ToolResult, tool


@tool(
    name="list_desks",
    domain="desks",
    description=(
        "List the desks available in Superdesk. Use this to resolve a desk name "
        "before placing an article on a specific desk."
    ),
    parameters={"type": "object", "properties": {}},
)
async def list_desks(args, ctx: ToolContext) -> ToolResult:
    cursor = await superdesk.get_resource_service("desks").get_all_async()
    names = [d.get("name") async for d in cursor if d.get("name")]
    joined = ", ".join(names) if names else "(none)"
    return ToolResult(
        ok=True,
        summary=f"Found {len(names)} desk(s)",
        detail=joined,
        for_model=f"Available desks: {joined}",
        data={"desks": names},
    )
