import superdesk

from ..base import ToolContext, ToolResult, tool


@tool(
    name="list_categories",
    domain="vocabularies",
    description="List the available content categories (ANPA categories) with their qcodes.",
    parameters={"type": "object", "properties": {}},
)
async def list_categories(args, ctx: ToolContext) -> ToolResult:
    vocab = await superdesk.get_resource_service("vocabularies").find_one_async(
        req=None, _id="categories"
    )
    items = (vocab or {}).get("items") or []
    categories = [
        {"qcode": i.get("qcode"), "name": i.get("name")}
        for i in items
        if i.get("is_active", True)
    ]
    listing = ", ".join(f"{c['name']} ({c['qcode']})" for c in categories) or "(none)"
    return ToolResult(
        ok=True,
        summary=f"{len(categories)} categor(ies)",
        detail=listing,
        for_model=f"Available categories: {listing}",
        data={"categories": categories},
    )
