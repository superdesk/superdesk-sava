"""Provenance: what SAVA records on the items it creates or edits."""

from types import SimpleNamespace

import superdesk

from sava import agent
from sava.agent import run_agent
from sava.tools import provenance, run_tool
from sava.tools.base import ToolContext, ToolResult, tool

CTX = ToolContext(user={"_id": "u1", "user_type": "administrator"}, model="openai/gpt-oss-120b", conversation_id="c1")


def test_entry_records_tool_time_model_user_and_conversation():
    e = provenance.entry(CTX, "create_article")
    assert e["tool"] == "create_article"
    assert e["model"] == "openai/gpt-oss-120b"
    assert e["user"] == "u1"
    assert e["conversation"] == "c1"
    assert e["at"].startswith("20")
    assert provenance.entry(ToolContext(), "x")["user"] is None


def test_stamp_new_marks_created_and_keeps_other_extra(monkeypatch):
    monkeypatch.delenv("SAVA_PROVENANCE_TAG", raising=False)
    item = {"headline": "H", "extra": {"custom": 1}}
    provenance.stamp_new(item, CTX, "create_article")
    assert item["extra"]["custom"] == 1
    assert item["extra"]["sava"]["created"] is True
    assert [a["tool"] for a in item["extra"]["sava"]["actions"]] == ["create_article"]
    assert "subject" not in item  # tag off by default


def test_stamp_update_appends_and_preserves_created_flag(monkeypatch):
    monkeypatch.delenv("SAVA_PROVENANCE_TAG", raising=False)
    original = {"extra": {"sava": {"created": True, "actions": [{"tool": "create_article"}]}, "custom": 1}}
    updates = {"headline": "New"}
    provenance.stamp_update(updates, original, CTX, "update_article")
    assert updates["headline"] == "New"
    assert updates["extra"]["custom"] == 1
    assert updates["extra"]["sava"]["created"] is True
    assert [a["tool"] for a in updates["extra"]["sava"]["actions"]] == ["create_article", "update_article"]

    untouched = {"headline": "H"}
    updates = {}
    provenance.stamp_update(updates, untouched, CTX, "move_article")
    assert updates["extra"]["sava"]["created"] is False
    assert len(updates["extra"]["sava"]["actions"]) == 1


def test_tag_is_added_once_when_enabled(monkeypatch):
    monkeypatch.setenv("SAVA_PROVENANCE_TAG", "AI-assisted")
    monkeypatch.delenv("SAVA_PROVENANCE_SCHEME", raising=False)
    mark = {"qcode": "ai-assisted", "name": "AI-assisted", "scheme": "sava"}

    item = {"subject": [{"qcode": "01000000", "name": "arts"}]}
    provenance.stamp_new(item, CTX, "create_article")
    assert item["subject"] == [{"qcode": "01000000", "name": "arts"}, mark]

    updates = {}
    provenance.stamp_update(updates, item, CTX, "update_article")
    assert "subject" not in updates  # already tagged: don't rewrite the subject list

    updates = {"subject": [{"qcode": "x", "name": "y"}]}
    provenance.stamp_update(updates, {"subject": []}, CTX, "update_article")
    assert updates["subject"] == [{"qcode": "x", "name": "y"}, mark]  # merges with the model's own edit


def test_tag_qcode_is_slugified_and_scheme_configurable(monkeypatch):
    monkeypatch.setenv("SAVA_PROVENANCE_TAG", "Made with AI (beta)")
    monkeypatch.setenv("SAVA_PROVENANCE_SCHEME", "ai_marks")
    assert provenance.tag() == {"qcode": "made-with-ai-beta", "name": "Made with AI (beta)", "scheme": "ai_marks"}
    monkeypatch.setenv("SAVA_PROVENANCE_TAG", "   ")
    assert provenance.tag() is None


async def test_create_planning_item_writes_provenance(monkeypatch):
    monkeypatch.delenv("SAVA_PROVENANCE_TAG", raising=False)
    posted = []

    class _Planning:
        async def post_async(self, docs):
            for d in docs:
                d["_id"] = "p1"
            posted.extend(docs)

    monkeypatch.setattr(superdesk, "get_resource_service", lambda name: _Planning())
    res = await run_tool("create_planning_item", {"slugline": "budget"}, CTX)
    assert res.ok, res.for_model
    record = posted[0]["extra"]["sava"]
    assert record["created"] is True
    assert record["actions"][0]["tool"] == "create_planning_item"
    assert record["actions"][0]["conversation"] == "c1"


async def test_run_agent_gives_tools_the_model_and_conversation(monkeypatch):
    monkeypatch.setenv("SAVA_OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("SAVA_MODEL", "vendor/model-x")
    seen = {}

    @tool(name="sava_test_ctx_probe", description="probe", parameters={"type": "object", "properties": {}})
    async def _probe(args, ctx):
        seen["model"], seen["conversation"] = ctx.model, ctx.conversation_id
        return ToolResult(ok=True, summary="ok", for_model="ok")

    class _Completions:
        def __init__(self):
            self.n = 0

        async def create(self, **kwargs):
            self.n += 1
            if self.n == 1:
                tc = SimpleNamespace(id="c1", function=SimpleNamespace(name="sava_test_ctx_probe", arguments="{}"))
                msg = SimpleNamespace(content="", tool_calls=[tc])
            else:
                msg = SimpleNamespace(content="Done.", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(
        agent, "_build_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    )
    await run_agent("go", user={"_id": "u1"}, conversation_id="conv-9")
    assert seen == {"model": "vendor/model-x", "conversation": "conv-9"}
