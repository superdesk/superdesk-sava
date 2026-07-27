"""Agent loop internals: reply cleaning, history handling, confirmation gating."""

import pytest

from sava.agent import (
    _build_pending,
    _clean_reply,
    _resolve_tool_calls,
    _sanitize_history,
    _trim_history,
)
from sava.tools.base import Tool, ToolContext, ToolResult, tool


# A confirmation-gated tool used by the _resolve_tool_calls tests. Registered at
# import so it exists regardless of test order.
@tool(
    name="sava_test_gated",
    description="gated",
    parameters={"type": "object", "properties": {}},
    requires_confirmation=True,
    confirm_title="Sure?",
    confirm_label="Yes",
)
async def _gated(args, ctx):
    return ToolResult(ok=True, summary="ran", for_model="ran")


def _assistant_call(call_id):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": call_id, "type": "function", "function": {"name": "sava_test_gated", "arguments": "{}"}}],
    }


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("finalCreated the article", "Created the article"),
        ("analysis Something happened", "Something happened"),
        ("assistant Done", "Done"),
        ("commentary Note this", "Note this"),
        # Regression: a real word starting with a channel name must survive intact
        # (the earlier IGNORECASE bug turned "Finally" into "ly").
        ("Finally, we are done", "Finally, we are done"),
        ("", ""),
        ("Just a normal reply", "Just a normal reply"),
    ],
)
def test_clean_reply(raw, expected):
    assert _clean_reply(raw) == expected


def test_sanitize_history_filters_non_dicts_and_roleless():
    hist = [
        {"role": "user", "content": "hi"},
        "garbage",
        {"no_role": 1},
        {"role": "assistant", "content": "yo"},
    ]
    assert _sanitize_history(hist) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]


def test_sanitize_history_non_list():
    assert _sanitize_history(None) == []
    assert _sanitize_history("nope") == []


def test_trim_history_bounds_and_trims_to_user_boundary(monkeypatch):
    monkeypatch.setenv("SAVA_MAX_HISTORY_MESSAGES", "5")
    convo = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "tool", "content": "t"},
        {"role": "assistant", "content": "a3"},
    ]
    out = _trim_history(convo)
    # Last 5 = [a1, u2, a2, t, a3]; leading non-user (a1) is dropped so a
    # tool-call/result pair is never split at the head.
    assert out[0]["role"] == "user"
    assert {m["content"] for m in out} == {"u2", "a2", "t", "a3"}


def test_build_pending_links_article_to_monitoring():
    t = Tool(
        name="publish_article",
        description="",
        parameters={},
        handler=None,
        requires_confirmation=True,
        confirm_title="Publish?",
        confirm_label="Publish",
    )
    pending = _build_pending("tc1", t, {"article_id": "xyz"}, ToolContext())
    assert pending["id"] == "tc1"
    assert pending["tool"] == "publish_article"
    assert pending["title"] == "Publish?"
    assert pending["confirm_label"] == "Publish"
    assert pending["links"][0]["route"].startswith("/workspace/monitoring?item=xyz")


def test_build_pending_links_event_to_planning_with_default_title():
    t = Tool(name="post_event", description="", parameters={}, handler=None, requires_confirmation=True)
    pending = _build_pending("tc2", t, {"event_id": "e1"}, ToolContext())
    assert pending["links"][0] == {"label": "Open planning", "route": "/planning"}
    assert pending["title"] == "Run post_event?"  # confirm_title None -> default


async def test_resolve_tool_calls_pauses_on_confirmation():
    messages = [_assistant_call("call_1")]
    actions = []
    pending = await _resolve_tool_calls(messages, actions, ToolContext(), approved=set(), denied=set())
    assert pending is not None
    assert pending["tool"] == "sava_test_gated"
    assert pending["title"] == "Sure?"
    # Nothing executed while awaiting a decision.
    assert all(m["role"] != "tool" for m in messages)
    assert actions == []


async def test_resolve_tool_calls_runs_when_approved():
    messages = [_assistant_call("call_2")]
    actions = []
    pending = await _resolve_tool_calls(messages, actions, ToolContext(), approved={"call_2"}, denied=set())
    assert pending is None
    assert any(m["role"] == "tool" and m["tool_call_id"] == "call_2" for m in messages)
    assert actions and actions[0]["ok"] is True


async def test_resolve_tool_calls_records_denial():
    messages = [_assistant_call("call_3")]
    actions = []
    pending = await _resolve_tool_calls(messages, actions, ToolContext(), approved=set(), denied={"call_3"})
    assert pending is None
    tool_msgs = [m for m in messages if m["role"] == "tool"]
    assert tool_msgs and "declined" in tool_msgs[0]["content"].lower()
    assert actions[0]["ok"] is False


async def test_resolve_tool_calls_noop_without_trailing_tool_calls():
    messages = [{"role": "assistant", "content": "just text"}]
    pending = await _resolve_tool_calls(messages, [], ToolContext(), approved=set(), denied=set())
    assert pending is None
