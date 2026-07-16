from ..base import ToolContext, ToolResult, tool
from ..lookups import get_content_profile


@tool(
    name="describe_content_profile",
    domain="profiles",
    description=(
        "Describe a content profile's fields — which are required vs optional — so "
        "you can ask the user for the necessary values before creating an article."
    ),
    parameters={
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Profile id or label (e.g. 'Text').",
            },
        },
        "required": ["profile"],
    },
)
async def describe_content_profile(args, ctx: ToolContext) -> ToolResult:
    identifier = (args.get("profile") or "").strip()
    profile = await get_content_profile(identifier)
    if profile is None:
        return ToolResult(
            ok=False,
            summary="Profile not found",
            for_model=f"No content profile matched '{identifier}'.",
        )

    schema = profile.get("schema") or {}
    required, optional = [], []
    for field_name, cfg in schema.items():
        if cfg is None:
            continue
        if isinstance(cfg, dict) and cfg.get("required"):
            required.append(field_name)
        else:
            optional.append(field_name)

    label = profile.get("label") or str(profile.get("_id"))
    return ToolResult(
        ok=True,
        summary=f"'{label}' — required: {', '.join(required) or 'none'}",
        for_model=(
            f"Content profile '{label}' (id={profile.get('_id')}). "
            f"Required fields: {', '.join(required) or 'none'}. "
            f"Optional fields: {', '.join(optional) or 'none'}."
        ),
        data={"profile_id": str(profile.get("_id")), "required": required, "optional": optional},
    )
