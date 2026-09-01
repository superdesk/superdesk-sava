"""Shared helpers for event workflow actions (not tools).

The event workflow actions (cancel / postpone / reschedule / update_time) require
the event to be locked by the current user+session with a matching lock_action;
the planning ``process_*`` function releases the lock when it completes. If it
fails part-way the lock would otherwise stay held by SAVA's session, so
``run_event_action`` releases it before re-raising. Imports of superdesk-planning
internals are kept lazy so the tools package still loads in environments where
planning is not installed.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

import superdesk

logger = logging.getLogger(__name__)

EventProcess = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Any]]


async def _find_event(event_id: str) -> Optional[Dict[str, Any]]:
    return await superdesk.get_resource_service("events").find_one_async(req=None, _id=event_id)


def _lock_context() -> Tuple[Any, Any, Any]:
    """(lock service, current user id, current session id) for this request."""
    from planning.item_lock import LockService
    from apps.common.components.utils import get_component
    from apps.archive.common import get_user, get_auth

    return get_component(LockService), get_user(required=True)["_id"], get_auth()["_id"]


async def run_event_action(
    event_id: str, lock_action: str, process: EventProcess, updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Lock the event for ``lock_action``, run ``process(updates, locked_item)``, and
    release the lock if that raises. Returns the locked item, or None if the event
    doesn't exist."""
    item = await _find_event(event_id)
    if item is None:
        return None

    lock_service, user_id, session_id = _lock_context()
    await lock_service.validate_relationship_locks(item, "events")
    locked = await lock_service.lock(item, user_id, session_id, lock_action, "events")
    try:
        await process(updates, locked)
    except Exception:
        try:
            await lock_service.unlock(locked, user_id, session_id, "events")
        except Exception:  # noqa: BLE001 - report the original failure, not the cleanup
            logger.exception("SAVA: failed to release lock on event %s after %s failed", event_id, lock_action)
        raise
    return locked


def parse_dt(value: str):
    """Parse an ISO datetime string the way the planning endpoints do."""
    from eve_elastic.elastic import parse_date

    return parse_date(value)
