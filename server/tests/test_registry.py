"""Tool framework: registration, schema advertisement, and execution safety."""

import logging

from sava.tools.base import (
    Tool,
    ToolContext,
    ToolLink,
    ToolResult,
    _REGISTRY,
    get_openai_tools,
    get_tool,
    run_tool,
    tool,
)


def test_tool_decorator_registers():
    @tool(name="sava_test_noop", description="noop", parameters={"type": "object", "properties": {}})
    async def _noop(args, ctx):
        return ToolResult(ok=True, summary="ok", for_model="ok")

    assert "sava_test_noop" in _REGISTRY
    t = get_tool("sava_test_noop")
    assert isinstance(t, Tool)
    assert t.description == "noop"
    assert t.domain == "general"
    assert t.requires_confirmation is False


def test_get_openai_tools_shape():
    schemas = get_openai_tools()
    assert isinstance(schemas, list) and schemas
    for schema in schemas:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert {"name", "description", "parameters"} <= set(fn)
        assert isinstance(fn["name"], str) and fn["name"]
        assert isinstance(fn["parameters"], dict)


def test_duplicate_name_warns_and_overrides(caplog):
    @tool(name="sava_test_dup", description="first", parameters={"type": "object", "properties": {}})
    async def _first(args, ctx):
        return ToolResult(ok=True, summary="ok", for_model="ok")

    with caplog.at_level(logging.WARNING):

        @tool(name="sava_test_dup", description="second", parameters={"type": "object", "properties": {}})
        async def _second(args, ctx):
            return ToolResult(ok=True, summary="ok", for_model="ok")

    assert any("already registered" in r.getMessage() for r in caplog.records)
    assert get_tool("sava_test_dup").description == "second"


async def test_run_tool_success():
    @tool(name="sava_test_ok", description="ok", parameters={"type": "object", "properties": {}})
    async def _ok(args, ctx):
        return ToolResult(ok=True, summary="did it", for_model="did it", data={"x": 1})

    res = await run_tool("sava_test_ok", {}, ToolContext())
    assert res.ok is True
    assert res.summary == "did it"


async def test_run_tool_unknown_is_graceful():
    res = await run_tool("sava_no_such_tool", {}, ToolContext())
    assert res.ok is False
    assert "unknown" in res.for_model.lower()


async def test_run_tool_catches_handler_exception():
    @tool(name="sava_test_boom", description="boom", parameters={"type": "object", "properties": {}})
    async def _boom(args, ctx):
        raise RuntimeError("kaboom")

    res = await run_tool("sava_test_boom", {}, ToolContext())
    assert res.ok is False
    assert "kaboom" in (res.detail or "") or "kaboom" in res.for_model


def test_toolresult_action_dict():
    res = ToolResult(ok=True, summary="s", for_model="m", detail="d", links=[ToolLink("L", "/r")])
    assert res.action_dict("mytool") == {
        "tool": "mytool",
        "ok": True,
        "summary": "s",
        "detail": "d",
        "links": [{"label": "L", "route": "/r"}],
    }


def test_toolcontext_link_to_item():
    link = ToolContext().link_to_item("abc123")
    assert link.route == "/workspace/monitoring?item=abc123&action=edit"
    assert link.to_dict() == {"label": "Open in monitoring", "route": link.route}


# --- privilege gating ---------------------------------------------------------


@tool(
    name="sava_test_privileged",
    description="needs publish",
    parameters={"type": "object", "properties": {}},
    privilege="publish",
)
async def _privileged(args, ctx):
    return ToolResult(ok=True, summary="published", for_model="published")


async def test_privileged_tool_denied_without_privilege():
    user = {"_id": "u1", "user_type": "user", "privileges": {}}
    res = await run_tool("sava_test_privileged", {}, ToolContext(user=user))
    assert res.ok is False
    assert "publish" in res.for_model
    assert res.summary == "Not permitted"


async def test_privileged_tool_runs_with_user_privilege():
    user = {"_id": "u1", "user_type": "user", "privileges": {"publish": 1}}
    res = await run_tool("sava_test_privileged", {}, ToolContext(user=user))
    assert res.ok is True
    assert res.summary == "published"


async def test_privileged_tool_runs_for_admin():
    user = {"_id": "u1", "user_type": "administrator"}
    res = await run_tool("sava_test_privileged", {}, ToolContext(user=user))
    assert res.ok is True


async def test_privileged_tool_skips_check_without_user():
    # No user = system/worker context, mirroring Superdesk's own check_permissions.
    res = await run_tool("sava_test_privileged", {}, ToolContext())
    assert res.ok is True


def test_every_write_tool_declares_a_privilege():
    """Any tool that can change Superdesk state must be privilege-gated, since the
    service calls bypass the HTTP-layer check. Read-only tools are the exception."""
    read_only_prefixes = ("find_", "list_", "search_", "get_", "describe_")
    missing = [
        name
        for name, t in _REGISTRY.items()
        if not name.startswith("sava_test_") and not name.startswith(read_only_prefixes) and not t.privilege
    ]
    assert missing == []


def test_get_openai_tools_cache_refreshes_on_new_registration():
    before = get_openai_tools()
    assert get_openai_tools() is before  # cached between calls

    @tool(name="sava_test_late", description="late", parameters={"type": "object", "properties": {}})
    async def _late(args, ctx):
        return ToolResult(ok=True, summary="ok", for_model="ok")

    after = get_openai_tools()
    assert after is not before
    assert "sava_test_late" in {s["function"]["name"] for s in after}
