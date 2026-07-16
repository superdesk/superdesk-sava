from typing import Any, Dict

import superdesk
from superdesk.utc import utcnow

from ..base import ToolContext, ToolLink, ToolResult, tool


def _build_coverage(spec: Dict[str, Any]) -> Dict[str, Any]:
    planning: Dict[str, Any] = {
        "g2_content_type": spec.get("g2_content_type") or spec.get("type") or "text",
    }
    if spec.get("slugline"):
        planning["slugline"] = spec["slugline"]
    if spec.get("scheduled"):
        planning["scheduled"] = spec["scheduled"]
    return {"planning": planning}


@tool(
    name="create_planning_item",
    domain="planning",
    description=(
        "Create a planning item. `planning_date` is an ISO datetime (defaults to now). "
        "You can include coverages up front, each with a g2_content_type (see list_coverage_types)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "slugline": {"type": "string"},
            "headline": {"type": "string"},
            "name": {"type": "string"},
            "description_text": {"type": "string"},
            "planning_date": {"type": "string", "description": "ISO datetime; defaults to now."},
            "coverages": {
                "type": "array",
                "items": {"type": "object"},
                "description": 'Optional coverages, e.g. [{"g2_content_type": "text", "slugline": "ai-conf"}].',
            },
        },
        "required": ["slugline"],
    },
)
async def create_planning_item(args, ctx: ToolContext) -> ToolResult:
    slugline = (args.get("slugline") or "").strip()
    if not slugline:
        return ToolResult(ok=False, summary="No slugline", for_model="A slugline is required to create a planning item.")

    item: Dict[str, Any] = {
        "slugline": slugline,
        "planning_date": args.get("planning_date") or utcnow().isoformat(),
    }
    for key in ("headline", "name", "description_text"):
        if args.get(key):
            item[key] = args[key]

    coverages = args.get("coverages")
    if isinstance(coverages, list) and coverages:
        item["coverages"] = [_build_coverage(c) for c in coverages if isinstance(c, dict)]

    await superdesk.get_resource_service("planning").post_async([item])
    planning_id = str(item["_id"])
    cov_count = len(item.get("coverages") or [])
    return ToolResult(
        ok=True,
        summary=f"Created planning item “{slugline}”" + (f" with {cov_count} coverage(s)" if cov_count else ""),
        for_model=(
            f"Created planning item id={planning_id} slugline='{slugline}' "
            f"planning_date={item['planning_date']} coverages={cov_count}."
        ),
        data={"planning_id": planning_id, "coverages": cov_count},
        links=[ToolLink(label="Open planning", route="/planning")],
    )
