import superdesk

from ..base import ToolContext, ToolResult, tool


@tool(
    name="list_coverage_types",
    domain="vocabularies",
    description="List the available coverage content types (text, picture, video, ...) for planning coverages.",
    parameters={"type": "object", "properties": {}},
)
async def list_coverage_types(args, ctx: ToolContext) -> ToolResult:
    vocab = await superdesk.get_resource_service("vocabularies").find_one_async(
        req=None, _id="g2_content_type"
    )
    items = (vocab or {}).get("items") or []
    types = [
        {"qcode": i.get("qcode"), "name": i.get("name")}
        for i in items
        if i.get("is_active", True)
    ]
    listing = ", ".join(f"{t['name']} ({t['qcode']})" for t in types) or "(none)"
    return ToolResult(
        ok=True,
        summary=f"{len(types)} coverage type(s)",
        detail=listing,
        for_model=f"Available coverage types (g2_content_type qcodes): {listing}",
        data={"coverage_types": types},
    )
