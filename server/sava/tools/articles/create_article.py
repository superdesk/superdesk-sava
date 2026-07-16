from typing import Any, Dict

import superdesk
from apps.archive.common import ARCHIVE, insert_into_versions_async
from superdesk.metadata.item import CONTENT_STATE
from superdesk.resource_fields import VERSION
from superdesk.utc import utcnow

from ..base import ToolContext, ToolResult, tool
from ..lookups import get_content_profile, resolve_desk_stage


@tool(
    name="create_article",
    domain="articles",
    description=(
        "Create a new article. Pick a content profile (see list_content_profiles) and "
        "pass its fields (see describe_content_profile) in `fields`. Ask the user for any "
        "required field they haven't given. Returns the new article id and a link to open it."
    ),
    parameters={
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Content profile id or label (e.g. 'Text'). Optional; omit to use the instance default.",
            },
            "fields": {
                "type": "object",
                "description": (
                    "Field values keyed by field name, e.g. "
                    '{"headline": "...", "slugline": "...", "body_html": "<p>...</p>"}.'
                ),
            },
            "desk": {
                "type": "string",
                "description": "Desk name to place the article on. Optional; defaults to the user's desk.",
            },
        },
        "required": ["fields"],
    },
)
async def create_article(args, ctx: ToolContext) -> ToolResult:
    fields = args.get("fields")
    if not isinstance(fields, dict):
        fields = {}

    headline = (fields.get("headline") or "").strip()

    profile_doc = None
    if args.get("profile"):
        profile_doc = await get_content_profile(str(args["profile"]).strip())

    desk, stage_id = await resolve_desk_stage(args.get("desk"), ctx.user)

    item: Dict[str, Any] = {
        "type": "text",
        "state": CONTENT_STATE.SUBMITTED,
        # Version fields, matching Superdesk's internal fetch_item, so the item is
        # publishable (publish reads _current_version).
        VERSION: 1,
        "versioncreated": utcnow(),
    }
    for key, value in fields.items():
        if value is not None:
            item[key] = value
    if profile_doc is not None:
        item["profile"] = profile_doc.get("_id")
    if desk is not None:
        item["task"] = {"desk": desk["_id"], "stage": stage_id}

    await superdesk.get_resource_service(ARCHIVE).post_async([item])
    await insert_into_versions_async(doc=item)

    article_id = str(item["_id"])
    title = headline or "(untitled)"
    desk_name = desk.get("name") if desk else "(no desk)"
    return ToolResult(
        ok=True,
        summary=f"Created “{title}” on {desk_name}",
        detail=f"id {article_id}",
        for_model=(
            f"Created article id={article_id} headline='{title}' "
            f"profile='{item.get('profile')}' on desk '{desk_name}', state=submitted."
        ),
        data={"article_id": article_id, "headline": title},
        links=[ctx.link_to_item(article_id)],
    )
