"""Event workflow actions: the lock taken for an action is released if it fails."""

import pytest

from sava.tools.events import _actions


class _FakeLockService:
    def __init__(self):
        self.locked = None
        self.unlocked = None
        self.validated = False

    async def validate_relationship_locks(self, item, resource):
        self.validated = True

    async def lock(self, item, user_id, session_id, action, resource):
        self.locked = (item["_id"], user_id, session_id, action, resource)
        return {**item, "lock_user": user_id, "lock_session": session_id, "lock_action": action}

    async def unlock(self, item, user_id, session_id, resource):
        self.unlocked = (item["_id"], user_id, session_id, resource)
        return item


@pytest.fixture
def lock_service(monkeypatch):
    svc = _FakeLockService()
    monkeypatch.setattr(_actions, "_lock_context", lambda: (svc, "user1", "sess1"))

    async def find(event_id):
        return {"_id": event_id, "name": "Launch"} if event_id == "e1" else None

    monkeypatch.setattr(_actions, "_find_event", find)
    return svc


async def test_returns_none_for_missing_event(lock_service):
    async def process(updates, original):
        raise AssertionError("must not run")

    assert await _actions.run_event_action("nope", "cancel", process, {}) is None
    assert lock_service.locked is None


async def test_locks_runs_process_and_keeps_lock_for_process_to_release(lock_service):
    seen = {}

    async def process(updates, original):
        seen["updates"] = updates
        seen["original"] = original

    result = await _actions.run_event_action("e1", "cancel", process, {"reason": "rain"})
    assert lock_service.validated is True
    assert lock_service.locked == ("e1", "user1", "sess1", "cancel", "events")
    assert seen["updates"] == {"reason": "rain"}
    assert seen["original"]["lock_action"] == "cancel"
    assert result is seen["original"]
    # On success the planning process_* function releases the lock itself.
    assert lock_service.unlocked is None


async def test_releases_lock_and_reraises_when_process_fails(lock_service):
    async def process(updates, original):
        raise RuntimeError("validation failed")

    with pytest.raises(RuntimeError, match="validation failed"):
        await _actions.run_event_action("e1", "postpone", process, {})
    assert lock_service.locked[3] == "postpone"
    assert lock_service.unlocked == ("e1", "user1", "sess1", "events")


async def test_unlock_failure_does_not_mask_original_error(lock_service):
    async def process(updates, original):
        raise RuntimeError("original")

    async def bad_unlock(*a, **k):
        raise RuntimeError("unlock broke")

    lock_service.unlock = bad_unlock
    with pytest.raises(RuntimeError, match="original"):
        await _actions.run_event_action("e1", "reschedule", process, {})
