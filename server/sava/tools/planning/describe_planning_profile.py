from ..base import ToolContext, ToolResult, tool
from ..lookups import get_planning_profile, split_required_optional

_PROFILES = ("event", "planning", "coverage")


@tool(
    name="describe_planning_profile",
    domain="planning",
    description=(
        "Describe the fields — required vs optional — for an event, planning item, or "
        "coverage in THIS instance. These requirements are configured per-instance and "
        "can change, so check here before creating rather than assuming a fixed set."
    ),
    parameters={
        "type": "object",
        "properties": {
            "profile": {"type": "string", "enum": list(_PROFILES)},
        },
        "required": ["profile"],
    },
)
async def describe_planning_profile(args, ctx: ToolContext) -> ToolResult:
    name = (args.get("profile") or "").strip().lower()
    if name not in _PROFILES:
        return ToolResult(
            ok=False,
            summary="Unknown profile",
            for_model="profile must be one of: event, planning, coverage.",
        )

    profile = await get_planning_profile(name)
    if profile is None:
        return ToolResult(
            ok=False,
            summary="Profile not found",
            for_model=f"No '{name}' planning profile is configured on this instance.",
        )

    required, optional = split_required_optional(profile.get("schema"))
    return ToolResult(
        ok=True,
        summary=f"{name} — required: {', '.join(required) or 'none'}",
        for_model=(
            f"The '{name}' profile on this instance requires: {', '.join(required) or 'none'}. "
            f"Optional fields: {', '.join(optional) or 'none'}."
        ),
        data={"profile": name, "required": required, "optional": optional},
    )
