from ..base import ToolContext, ToolResult, tool
from ..lookups import find_user_by_name


@tool(
    name="find_user",
    domain="users",
    description=(
        "Resolve a person by name to a user id — needed before filtering articles "
        "or assignments by a specific author/assignee."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Full or partial name / username."},
        },
        "required": ["name"],
    },
)
async def find_user(args, ctx: ToolContext) -> ToolResult:
    name = (args.get("name") or "").strip()
    user = await find_user_by_name(name)
    if user is None:
        return ToolResult(
            ok=False,
            summary=f"No user matched '{name}'",
            for_model=f"No user found matching '{name}'.",
        )

    display = user.get("display_name") or user.get("username") or str(user.get("_id"))
    return ToolResult(
        ok=True,
        summary=f"Found user {display}",
        for_model=f"User '{display}' has id={user.get('_id')}.",
        data={"user_id": str(user.get("_id")), "display_name": display},
    )
