"""SAVA tools.

Each tool maps a natural-language intent to a real action against Superdesk's
own services, executed *as the logged-in user* so normal privilege checks apply.

The first end-to-end slice ships three tools:
    - list_desks       (read)
    - create_article   (write)
    - publish_article  (write)

``TOOLS`` holds the OpenAI-style function schemas advertised to the model.
``execute_tool`` dispatches a validated tool call to its implementation.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import superdesk
from apps.archive.common import ARCHIVE, insert_into_versions_async
from superdesk.metadata.item import CONTENT_STATE

logger = logging.getLogger(__name__)


# --- Tool schemas (advertised to the model) ----------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_desks",
            "description": (
                "List the desks available in Superdesk. Use this to discover valid "
                "desk names before creating an article on a specific desk."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_article",
            "description": (
                "Create a new text article (content item) in Superdesk. Returns the "
                "new article id, which you can pass to publish_article."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "headline": {
                        "type": "string",
                        "description": "The article headline.",
                    },
                    "body_html": {
                        "type": "string",
                        "description": "Article body as HTML. Optional.",
                    },
                    "slugline": {
                        "type": "string",
                        "description": "Short slug identifying the story. Optional.",
                    },
                    "desk": {
                        "type": "string",
                        "description": (
                            "Name of the desk to place the article on. Optional; "
                            "defaults to the user's desk or the first available desk."
                        ),
                    },
                },
                "required": ["headline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "publish_article",
            "description": "Publish an existing article, identified by its id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "string",
                        "description": "The id of the article to publish.",
                    },
                },
                "required": ["article_id"],
            },
        },
    },
]


# --- Helpers -----------------------------------------------------------------


async def _resolve_desk_stage(
    desk_name: Optional[str], user: Optional[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], Any]:
    """Resolve a desk (and a stage on it) to place a new article on.

    Order of preference: named desk (exact, then case-insensitive) ->
    the user's own desk -> the first available desk.
    """
    desks_service = superdesk.get_resource_service("desks")
    desk: Optional[Dict[str, Any]] = None

    if desk_name:
        desk = await desks_service.find_one_async(req=None, name=desk_name)
        if desk is None:
            cursor = await desks_service.get_all_async()
            async for candidate in cursor:
                if (candidate.get("name") or "").lower() == desk_name.lower():
                    desk = candidate
                    break

    if desk is None and user and user.get("desk"):
        desk = await desks_service.find_one_async(req=None, _id=user["desk"])

    if desk is None:
        cursor = await desks_service.get_all_async()
        async for candidate in cursor:
            desk = candidate
            break

    if desk is None:
        return None, None

    stage_id = desk.get("working_stage") or desk.get("incoming_stage")
    return desk, stage_id


# --- Tool implementations ----------------------------------------------------


async def list_desks(
    args: Dict[str, Any], user: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    desks_service = superdesk.get_resource_service("desks")
    cursor = await desks_service.get_all_async()
    names = [d.get("name") async for d in cursor if d.get("name")]
    joined = ", ".join(names) if names else "(none)"
    return {
        "ok": True,
        "tool": "list_desks",
        "summary": f"Found {len(names)} desk(s)",
        "detail": joined,
        "for_model": f"Available desks: {joined}",
    }


async def create_article(
    args: Dict[str, Any], user: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    headline = (args.get("headline") or "").strip()
    if not headline:
        return {
            "ok": False,
            "tool": "create_article",
            "summary": "No headline provided",
            "for_model": "Error: headline is required to create an article.",
        }

    desk, stage_id = await _resolve_desk_stage(args.get("desk"), user)

    item: Dict[str, Any] = {
        "type": "text",
        "headline": headline,
        "body_html": args.get("body_html") or "<p></p>",
        "state": CONTENT_STATE.SUBMITTED,
    }
    if args.get("slugline"):
        item["slugline"] = args["slugline"]
    if desk is not None:
        item["task"] = {"desk": desk["_id"], "stage": stage_id}

    await superdesk.get_resource_service(ARCHIVE).post_async([item])
    await insert_into_versions_async(doc=item)

    article_id = str(item["_id"])
    desk_name = desk.get("name") if desk else "(no desk)"
    return {
        "ok": True,
        "tool": "create_article",
        "summary": f"Created article “{headline}” on desk {desk_name}",
        "detail": f"id {article_id}",
        "article_id": article_id,
        "for_model": (
            f"Created article id={article_id} headline='{headline}' "
            f"on desk '{desk_name}', state=submitted."
        ),
    }


async def publish_article(
    args: Dict[str, Any], user: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    article_id = args.get("article_id")
    if not article_id:
        return {
            "ok": False,
            "tool": "publish_article",
            "summary": "No article id provided",
            "for_model": "Error: article_id is required to publish.",
        }

    await superdesk.get_resource_service("archive_publish").patch_async(article_id, {})
    return {
        "ok": True,
        "tool": "publish_article",
        "summary": "Published article",
        "detail": f"id {article_id}",
        "for_model": f"Published article id={article_id}.",
    }


# --- Dispatch ----------------------------------------------------------------

_TOOL_FUNCTIONS = {
    "list_desks": list_desks,
    "create_article": create_article,
    "publish_article": publish_article,
}


async def execute_tool(
    name: str, args: Dict[str, Any], user: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Run a single tool call, returning a result dict.

    The result always carries ``ok``, ``tool``, ``summary`` and ``for_model``
    (the string fed back to the model). ``detail`` and ``article_id`` are
    optional. Exceptions are caught and surfaced as failed actions so one bad
    tool call never crashes the whole request.
    """
    fn = _TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {
            "ok": False,
            "tool": name,
            "summary": f"Unknown tool: {name}",
            "for_model": f"Error: unknown tool '{name}'.",
        }

    try:
        return await fn(args, user)
    except Exception as exc:  # noqa: BLE001 - surface any tool failure to the model
        logger.exception("SAVA tool '%s' failed", name)
        return {
            "ok": False,
            "tool": name,
            "summary": f"{name} failed",
            "detail": str(exc),
            "for_model": f"Error running {name}: {exc}",
        }
