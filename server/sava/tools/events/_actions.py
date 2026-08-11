"""Shared helpers for event workflow actions (not tools).

The event workflow actions (cancel / postpone / reschedule / update_time) require
the event to be locked by the current user+session with a matching lock_action;
the process_* function releases the lock when it completes. Imports of
superdesk-planning internals are kept lazy so the tools package still loads in
environments where planning is not installed.
"""

import superdesk


async def lock_event(event_id: str, lock_action: str):
    """Lock an event for the given action, returning the locked doc (with lock
    fields set) or None if the event doesn't exist."""
    from planning.item_lock import LockService
    from apps.common.components.utils import get_component
    from apps.archive.common import get_user, get_auth

    service = superdesk.get_resource_service("events")
    item = await service.find_one_async(req=None, _id=event_id)
    if item is None:
        return None

    lock_service = get_component(LockService)
    user_id = get_user(required=True)["_id"]
    session_id = get_auth()["_id"]
    await lock_service.validate_relationship_locks(item, "events")
    return await lock_service.lock(item, user_id, session_id, lock_action, "events")


def parse_dt(value: str):
    """Parse an ISO datetime string the way the planning endpoints do."""
    from eve_elastic.elastic import parse_date

    return parse_date(value)
