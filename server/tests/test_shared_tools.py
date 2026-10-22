"""The shared tools as SAVA runs them: as the user, asking first where they must, shown as cards and links."""

import base64
import json
import re
from types import SimpleNamespace
import pytest
from aioresponses import aioresponses
from sava import shared_tools, views
from sava.results import Pending

URL = "http://superdesk.test/api"
DESKS = [{"_id": "d1", "name": "Politics", "working_stage": "s1", "incoming_stage": "s2"}]
ITEM = {
    "_id": "item-1", "_etag": "e1", "_current_version": 3, "state": "in_progress", "type": "text", "profile": "text",
    "headline": "Budget vote", "body_html": "<p>Four words of text.</p>", "word_count": 4,
    "task": {"desk": "d1", "stage": "s1"},
}  # fmt: skip


def collection(items):
    return {"_items": items, "_meta": {"total": len(items)}}


def matching(path: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(URL)}/{re.escape(path)}(\?.*)?$")


def sent(mocked, method: str, path: str) -> list:
    return [
        request.kwargs.get("json")
        for (used, url), requests in mocked.requests.items()
        if used == method and url.path == f"/api/{path}"
        for request in requests
    ]


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("SAVA_SUPERDESK_API_URL", URL)
    shared_tools._CACHE.clear()
    yield
    shared_tools._CACHE.clear()


@pytest.fixture
def mocked():
    with aioresponses() as mock:
        mock.get(matching("desks"), payload=collection(DESKS), repeat=True)
        mock.get(matching("stages"), payload=collection([{"_id": "s1", "name": "Working", "desk": "d1"}]), repeat=True)
        mock.get(matching("content_types/text"), payload={"_id": "text", "schema": {}, "editor": {}}, repeat=True)
        mock.get(matching("vocabularies"), payload=collection([]), repeat=True)
        yield mock


def names() -> set:
    return {schema["function"]["name"] for schema in shared_tools.schemas()}


def test_the_model_gets_the_configured_toolsets(monkeypatch):
    assert {"create_article", "create_event", "publish_item", "spike_event"} <= names()

    monkeypatch.setenv("SAVA_TOOLSETS", "discovery,search")
    monkeypatch.setenv("SAVA_ALLOW_PUBLISH", "0")
    assert "create_article" not in names() and {"list_desks", "search_content"} <= names()

    monkeypatch.setenv("SAVA_TOOLSETS", "publishing")
    assert "publish_item" not in names() and "validate_item" in names()


async def test_search_results_come_back_as_cards_with_desk_names(mocked):
    found = {**ITEM, "_type": "archive", "slugline": "budget", "_updated": "2026-10-01T10:00:00+0000"}
    mocked.get(re.compile(rf"^{re.escape(URL)}/search(\?.*)?$"), payload=collection([found]), repeat=True)

    async with shared_tools.toolbox("token") as tools:
        result = await tools.run("search_content", {"text": "budget"})

    assert result.ok and result.summary.startswith("Found 1")
    [card] = result.items
    assert (card.kind, card.id, card.title, card.desk) == ("article", "item-1", "Budget vote", "Politics")
    assert card.route == "/workspace/monitoring?item=item-1&action=edit"
    assert json.loads(result.for_model)["items"][0]["headline"] == "Budget vote"


async def test_a_created_article_records_sava_with_the_model_and_conversation(mocked):
    mocked.post(matching("archive"), payload={"_id": "new-1", "_etag": "n1", "state": "draft"}, status=201)

    async with shared_tools.toolbox("token", model="some-model", conversation_id="conv-1") as tools:
        result = await tools.run("create_article", {"headline": "Budget vote", "desk": "Politics"})

    assert result.ok and result.links[0].route == "/workspace/monitoring?item=new-1&action=edit"
    [action] = sent(mocked, "POST", "archive")[0]["extra"]["ai_provenance"]["actions"]
    assert (action["agent"], action["model"], action["conversation"]) == ("sava", "some-model", "conv-1")


async def test_a_tool_that_needs_consent_asks_and_acts_only_on_a_yes_to_that_question(mocked):
    mocked.get(matching("archive/item-1"), payload=ITEM, repeat=True)
    mocked.patch(matching("archive/spike/item-1"), payload={**ITEM, "_etag": "e2", "state": "spiked"}, repeat=True)

    async with shared_tools.toolbox("token") as tools:
        asked = await tools.run("spike_item", {"item_id": "item-1"})
        assert isinstance(asked, Pending) and asked.question.startswith("Spike “Budget vote”?")
        assert sent(mocked, "PATCH", "archive/spike/item-1") == []

        other = await tools.run("spike_item", {"item_id": "item-1"}, approved_question="Spike something else?")
        assert isinstance(other, Pending)  # a yes to another question is no yes to this one
        assert sent(mocked, "PATCH", "archive/spike/item-1") == []

        done = await tools.run("spike_item", {"item_id": "item-1"}, approved_question=asked.question)

    assert done.ok and len(sent(mocked, "PATCH", "archive/spike/item-1")) == 1


async def test_refusals_and_failures_reach_the_model_as_errors(mocked):
    mocked.get(matching("archive/nope"), status=404, repeat=True)

    async with shared_tools.toolbox("token") as tools:
        missing = await tools.run("get_item", {"item_id": "nope"})
        unknown = await tools.run("post_event", {})
        wrong = await tools.run("get_item", {"id": "x"})

    assert not missing.ok and missing.for_model.startswith("Error:")
    assert not unknown.ok and "no tool 'post_event'" in unknown.detail
    assert not wrong.ok and "cannot take" in wrong.detail


async def test_without_a_session_nothing_is_called():
    async with shared_tools.toolbox(None) as tools:
        result = await tools.run("list_desks", {})

    assert not result.ok and "session" in result.detail


@pytest.mark.parametrize(
    "header, token",
    [
        ("Basic " + base64.b64encode(b"abc123:").decode(), "abc123"),
        ("Bearer abc123", "abc123"),
        ("abc123", "abc123"),
    ],
)
def test_the_session_token_is_read_as_superdesk_reads_it(header, token):
    request = SimpleNamespace(get_header=lambda name: header, storage=SimpleNamespace(session={}))
    assert views._session_token(request) == token


def test_without_a_header_the_session_cookie_is_used():
    request = SimpleNamespace(get_header=lambda name: None, storage=SimpleNamespace(session={"session_token": "s1"}))
    assert views._session_token(request) == "s1"
