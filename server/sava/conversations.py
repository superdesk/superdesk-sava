"""Persistent, per-user chat history.

Each conversation stores two views of the same chat: ``messages`` is the
model-facing history the agent loop consumes (already trimmed to the configured
cap), and ``turns`` is what the UI renders (every user prompt, assistant reply
and activity log, never trimmed). ``pending`` keeps an unanswered confirmation
so it survives a reload. Every read and write is scoped to the owning user.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pydantic import Field
from superdesk.core import get_current_async_app
from superdesk.core.resources import (
    MongoIndexOptions,
    MongoResourceConfig,
    ResourceConfig,
    ResourceModelWithObjectId,
    fields,
)

from .agent import _build_client
from .default_settings import get_setting

logger = logging.getLogger(__name__)

RESOURCE = "sava_conversations"
TITLE_MAX = 60
TITLE_TIMEOUT_SECONDS = 8
LIST_LIMIT = 200

TITLE_PROMPT = (
    "Write a short title (3 to 6 words) for a chat that starts with the user message "
    "and assistant reply below. Reply with the title only: no quotes, no trailing "
    "punctuation, no explanation."
)


class Conversation(ResourceModelWithObjectId):
    user: fields.ObjectId
    title: str = "New chat"
    title_is_auto: bool = True
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    turns: List[Dict[str, Any]] = Field(default_factory=list)
    pending: Optional[Dict[str, Any]] = None


conversations_resource = ResourceConfig(
    name=RESOURCE,
    data_class=Conversation,
    mongo=MongoResourceConfig(
        indexes=[MongoIndexOptions(name="user_updated", keys=[("user", 1), ("_updated", -1)], unique=False)],
    ),
)


def _service():
    return get_current_async_app().resources.get_resource_service(RESOURCE)


def _oid(value: Any) -> ObjectId:
    return value if isinstance(value, ObjectId) else ObjectId(str(value))


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if hasattr(value, "isoformat") else None


# --- titles ------------------------------------------------------------------


def fallback_title(prompt: str) -> str:
    """A title from the first line of the prompt, cut at a word boundary."""
    text = re.sub(r"\s+", " ", (prompt or "").strip().splitlines()[0] if (prompt or "").strip() else "").strip()
    if not text:
        return "New chat"
    if len(text) <= TITLE_MAX:
        return text
    cut = text[:TITLE_MAX].rsplit(" ", 1)[0] or text[:TITLE_MAX]
    return cut.rstrip(" ,;:-") + "…"


def _clean_title(text: str) -> str:
    title = re.sub(r"\s+", " ", (text or "").strip().splitlines()[0] if (text or "").strip() else "")
    title = title.strip().strip("\"'“”‘’").rstrip(".").strip()
    return title[:TITLE_MAX].strip()


async def generate_title(prompt: str, reply: str) -> Optional[str]:
    """Ask the model for a short title. Returns None on any failure so the
    caller keeps the fallback; a title is never worth failing a turn over."""
    client = _build_client()
    if client is None:
        return None
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=get_setting("SAVA_MODEL"),
                messages=[
                    {"role": "system", "content": TITLE_PROMPT},
                    {"role": "user", "content": f"User: {prompt[:1000]}\n\nAssistant: {(reply or '')[:1000]}"},
                ],
                temperature=0,
                max_tokens=24,
            ),
            TITLE_TIMEOUT_SECONDS,
        )
        title = _clean_title(response.choices[0].message.content or "")
    except Exception:  # noqa: BLE001 - best effort only
        logger.warning("SAVA: title generation failed", exc_info=True)
        return None
    return title or None


# --- storage -----------------------------------------------------------------


def summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Sidebar entry for a raw conversation document."""
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title") or "New chat",
        "created": _iso(doc.get("_created")),
        "updated": _iso(doc.get("_updated")),
        "pending": bool(doc.get("pending")),
    }


def detail(conv: Conversation) -> Dict[str, Any]:
    """Everything the UI needs to reopen a conversation."""
    return {
        "id": str(conv.id),
        "title": conv.title,
        "turns": conv.turns,
        "pending": conv.pending,
        "created": _iso(conv.created),
        "updated": _iso(conv.updated),
    }


async def list_for_user(user_id: Any, limit: int = LIST_LIMIT) -> List[Dict[str, Any]]:
    cursor = (
        _service()
        .mongo_async.find({"user": _oid(user_id)}, {"title": 1, "_created": 1, "_updated": 1, "pending": 1})
        .sort("_updated", -1)
        .limit(limit)
    )
    return [summary(doc) async for doc in cursor]


async def get_owned(conversation_id: Any, user_id: Any) -> Optional[Conversation]:
    """The conversation, only if it exists and belongs to ``user_id``."""
    try:
        oid = ObjectId(str(conversation_id))
    except Exception:  # noqa: BLE001 - malformed id
        return None
    conv = await _service().find_by_id(oid)
    if conv is None or conv.user != _oid(user_id):
        return None
    return conv


async def create(user_id: Any, title: str) -> Conversation:
    created = await _service().create([{"user": _oid(user_id), "title": title}])
    return created[0]


async def save_turn(
    conv: Conversation,
    messages: List[Dict[str, Any]],
    new_turns: List[Dict[str, Any]],
    pending: Optional[Dict[str, Any]],
    title: Optional[str] = None,
) -> None:
    updates: Dict[str, Any] = {"messages": messages, "turns": list(conv.turns) + new_turns, "pending": pending}
    if title:
        updates["title"] = title
    await _service().update(conv.id, updates)


async def rename(conv: Conversation, title: str) -> None:
    await _service().update(conv.id, {"title": title, "title_is_auto": False})


async def delete(conv: Conversation) -> None:
    await _service().delete(conv)
