import superdesk

from ..base import ToolContext, ToolResult, tool


@tool(
    name="list_content_profiles",
    domain="profiles",
    description=(
        "List the available article content profiles (e.g. Text, Basic). Use this "
        "before creating an article so you can pick the right profile with the user."
    ),
    parameters={"type": "object", "properties": {}},
)
async def list_content_profiles(args, ctx: ToolContext) -> ToolResult:
    cursor = await superdesk.get_resource_service("content_types").get_all_async()
    profiles = []
    async for p in cursor:
        profiles.append({"id": str(p.get("_id")), "label": p.get("label") or str(p.get("_id"))})

    listing = ", ".join(f"{p['label']} (id={p['id']})" for p in profiles) or "(none)"
    return ToolResult(
        ok=True,
        summary=f"Found {len(profiles)} content profile(s)",
        detail=listing,
        for_model=f"Available content profiles: {listing}",
        data={"profiles": profiles},
    )
