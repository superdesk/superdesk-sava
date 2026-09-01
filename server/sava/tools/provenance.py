"""Provenance: record on the item itself that SAVA acted on it, and on whose behalf.

Written under ``extra.sava`` (``extra`` is the free-form dict articles, events
and planning items all share, so no schema change). The human user stays the
item's creator; this only says which agent actions touched it::

    "extra": {"sava": {"created": true, "actions": [
        {"tool": "create_planning_item", "at": "...", "model": "...", "user": "...", "conversation": "..."}
    ]}}

Optionally (``SAVA_PROVENANCE_TAG``) the item also gets a visible, filterable
``subject`` tag such as "AI-assisted", under the ``SAVA_PROVENANCE_SCHEME``
vocabulary. Workflow actions (publish, spike, post, cancel ...) are not written
here, since a published or spiked item can't simply be patched; the
conversation store records those.
"""

import re
from typing import Any, Dict, List, Optional

from superdesk.utc import utcnow

from ..default_settings import get_setting
from .base import ToolContext

KEY = "sava"


def entry(ctx: ToolContext, tool_name: str) -> Dict[str, Any]:
    user_id = (ctx.user or {}).get("_id")
    return {
        "tool": tool_name,
        "at": utcnow().isoformat(),
        "model": ctx.model,
        "user": str(user_id) if user_id else None,
        "conversation": ctx.conversation_id,
    }


def tag() -> Optional[Dict[str, str]]:
    """The visible subject tag, or None when ``SAVA_PROVENANCE_TAG`` is unset."""
    name = get_setting("SAVA_PROVENANCE_TAG").strip()
    if not name:
        return None
    qcode = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "ai-assisted"
    return {"qcode": qcode, "name": name, "scheme": get_setting("SAVA_PROVENANCE_SCHEME").strip() or KEY}


def _tagged(subject: Any, mark: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
    """``subject`` with the tag appended, or None if it's already there."""
    current = [s for s in (subject or []) if isinstance(s, dict)]
    if any(s.get("qcode") == mark["qcode"] and s.get("scheme") == mark["scheme"] for s in current):
        return None
    return current + [dict(mark)]


def stamp_new(item: Dict[str, Any], ctx: ToolContext, tool_name: str) -> None:
    """Mark a document SAVA is about to create."""
    extra = dict(item.get("extra") or {})
    extra[KEY] = {"created": True, "actions": [entry(ctx, tool_name)]}
    item["extra"] = extra
    mark = tag()
    if mark is not None:
        tagged = _tagged(item.get("subject"), mark)
        if tagged is not None:
            item["subject"] = tagged


def stamp_update(updates: Dict[str, Any], original: Dict[str, Any], ctx: ToolContext, tool_name: str) -> None:
    """Add this action to the item's provenance as part of ``updates``."""
    extra = dict(original.get("extra") or {})
    record = dict(extra.get(KEY) or {})
    record.setdefault("created", False)
    record["actions"] = list(record.get("actions") or []) + [entry(ctx, tool_name)]
    extra[KEY] = record
    updates["extra"] = extra
    mark = tag()
    if mark is not None:
        tagged = _tagged(updates.get("subject", original.get("subject")), mark)
        if tagged is not None:
            updates["subject"] = tagged
