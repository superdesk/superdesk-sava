from typing import Any, Dict

import superdesk

from ..base import ToolContext, ToolLink, ToolResult, tool


@tool(
    name="add_coverage",
    domain="planning",
    description=(
        "Add a coverage to an existing planning item. Coverage type is a g2_content_type "
        "qcode (text/picture/video/…; see list_coverage_types)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "planning_id": {"type": "string"},
            "coverage_type": {"type": "string", "description": "g2_content_type qcode, e.g. 'text', 'picture'."},
            "slugline": {"type": "string", "description": "Coverage slugline. Optional."},
            "scheduled": {"type": "string", "description": "ISO datetime the coverage is due. Optional."},
        },
        "required": ["planning_id", "coverage_type"],
    },
)
async def add_coverage(args, ctx: ToolContext) -> ToolResult:
    planning_id = (args.get("planning_id") or "").strip()
    coverage_type = (args.get("coverage_type") or "text").strip()
    if not planning_id:
        return ToolResult(ok=False, summary="No planning id", for_model="A planning_id is required.")

    service = superdesk.get_resource_service("planning")
    item = await service.find_one_async(req=None, _id=planning_id)
    if item is None:
        return ToolResult(ok=False, summary="Planning item not found", for_model=f"No planning item with id {planning_id}.")

    coverages = list(item.get("coverages") or [])
    planning: Dict[str, Any] = {"g2_content_type": coverage_type}
    if args.get("slugline"):
        planning["slugline"] = args["slugline"]
    if args.get("scheduled"):
        planning["scheduled"] = args["scheduled"]
    coverages.append({"planning": planning})

    await service.patch_async(planning_id, {"coverages": coverages})
    return ToolResult(
        ok=True,
        summary=f"Added {coverage_type} coverage",
        for_model=f"Added a {coverage_type} coverage to planning item id={planning_id} (now {len(coverages)} coverage(s)).",
        data={"planning_id": planning_id, "coverages": len(coverages)},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
