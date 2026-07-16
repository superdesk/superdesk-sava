import re

import superdesk

from ..base import ToolContext, ToolResult, tool

_TAGS = re.compile(r"<[^>]+>")


@tool(
    name="get_article",
    domain="articles",
    description="Fetch a single article by id and return its headline, state and a text preview of the body.",
    parameters={
        "type": "object",
        "properties": {"article_id": {"type": "string"}},
        "required": ["article_id"],
    },
)
async def get_article(args, ctx: ToolContext) -> ToolResult:
    article_id = (args.get("article_id") or "").strip()
    if not article_id:
        return ToolResult(ok=False, summary="No id", for_model="Error: article_id is required.")

    item = await superdesk.get_resource_service("archive").find_one_async(req=None, _id=article_id)
    if item is None:
        item = await superdesk.get_resource_service("published").find_one_async(req=None, item_id=article_id)
    if item is None:
        return ToolResult(ok=False, summary="Not found", for_model=f"No article found with id {article_id}.")

    headline = item.get("headline") or item.get("slugline") or "(untitled)"
    text = _TAGS.sub(" ", item.get("body_html") or "").strip()
    snippet = (text[:600] + "…") if len(text) > 600 else text
    return ToolResult(
        ok=True,
        summary=f"{headline} — {item.get('state')}",
        for_model=(
            f"Article id={article_id} headline='{headline}' state={item.get('state')} "
            f"slugline='{item.get('slugline')}':\n{snippet}"
        ),
        data={"article_id": article_id, "headline": headline},
        links=[ctx.link_to_item(article_id)],
    )
