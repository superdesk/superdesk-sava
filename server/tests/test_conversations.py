"""Conversation store: title handling and API serialisation (no database)."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

from sava import conversations
from sava.conversations import Conversation, detail, fallback_title, generate_title, summary


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("Show me the articles I have authored", "Show me the articles I have authored"),
        ("  first line\nsecond line  ", "first line"),
        ("lots   of    spaces", "lots of spaces"),
        ("", "New chat"),
        ("   \n  ", "New chat"),
    ],
)
def test_fallback_title(prompt, expected):
    assert fallback_title(prompt) == expected


def test_fallback_title_cuts_long_prompts_at_a_word_boundary():
    prompt = "Create a planning item for tomorrow about the quarterly budget review meeting with the finance team"
    title = fallback_title(prompt)
    assert title.endswith("…")
    assert len(title) <= conversations.TITLE_MAX + 1
    assert not title[:-1].endswith(" ")
    assert prompt.startswith(title[:-1])


def _title_client(content):
    class _Completions:
        async def create(self, **kwargs):
            _title_client.kwargs = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))


async def test_generate_title_cleans_model_output(monkeypatch):
    monkeypatch.setattr(conversations, "_build_client", lambda: _title_client('"Budget review planning."\n'))
    assert await generate_title("plan the budget review", "Created it.") == "Budget review planning"
    assert _title_client.kwargs["max_tokens"] == 24
    assert "tools" not in _title_client.kwargs


@pytest.mark.parametrize("content", ["", "   ", None])
async def test_generate_title_returns_none_for_empty_output(monkeypatch, content):
    monkeypatch.setattr(conversations, "_build_client", lambda: _title_client(content))
    assert await generate_title("x", "y") is None


async def test_generate_title_swallows_failures(monkeypatch):
    class _Boom:
        async def create(self, **kwargs):
            raise RuntimeError("provider down")

    monkeypatch.setattr(
        conversations, "_build_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=_Boom()))
    )
    assert await generate_title("x", "y") is None


async def test_generate_title_without_client(monkeypatch):
    monkeypatch.setattr(conversations, "_build_client", lambda: None)
    assert await generate_title("x", "y") is None


def test_summary_and_detail_serialise_ids_and_dates():
    oid, user = ObjectId(), ObjectId()
    when = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    raw = {"_id": oid, "title": "Budget", "_created": when, "_updated": when, "pending": {"id": "c1"}}
    assert summary(raw) == {
        "id": str(oid),
        "title": "Budget",
        "created": "2026-09-01T10:00:00+00:00",
        "updated": "2026-09-01T10:00:00+00:00",
        "pending": True,
    }
    assert summary({"_id": oid})["title"] == "New chat"

    conv = Conversation(_id=oid, user=user, title="Budget", turns=[{"role": "user", "text": "hi"}], _created=when)
    out = detail(conv)
    assert out["id"] == str(oid)
    assert out["turns"] == [{"role": "user", "text": "hi"}]
    assert out["pending"] is None
    assert out["created"] == "2026-09-01T10:00:00+00:00"
    assert "user" not in out
