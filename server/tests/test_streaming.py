"""Streaming mode of the agent loop: event emission, tool-call reassembly, Stop."""

import asyncio
from types import SimpleNamespace

from sava import agent
from sava.agent import _complete, run_agent
from sava.tools.base import ToolResult, tool


@tool(name="sava_test_stream_noop", description="noop", parameters={"type": "object", "properties": {}})
async def _noop(args, ctx):
    return ToolResult(ok=True, summary="ran", for_model="ran")


def _chunk(content=None, tool_calls=None, usage=None, choices=True):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)] if choices else [], usage=usage)


def _frag(index, id=None, name=None, arguments=None):
    return SimpleNamespace(index=index, id=id, function=SimpleNamespace(name=name, arguments=arguments))


class _Stream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _streaming_client(turns):
    """Each item in ``turns`` is the chunk list for one model call, in order."""
    calls = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["stream"] is True
            return _Stream(turns.pop(0))

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions())), calls


async def test_complete_streams_text_and_reassembles_tool_calls():
    usage = SimpleNamespace(prompt_tokens=50, completion_tokens=7)
    chunks = [
        _chunk(content="Let me "),
        _chunk(content="look."),
        _chunk(tool_calls=[_frag(0, id="call_a", name="sava_test_stream_noop", arguments="")]),
        _chunk(tool_calls=[_frag(0, arguments='{"x":'), _frag(1, id="call_b", name="list_desks", arguments="{")]),
        _chunk(tool_calls=[_frag(0, arguments=" 1}"), _frag(1, arguments="}")]),
        _chunk(choices=False, usage=usage),
    ]
    client, _ = _streaming_client([chunks])
    events, partial = [], []

    async def on_event(e):
        events.append(e)

    content, tool_calls, got_usage = await _complete(client, "m", [], on_event, partial)
    assert content == "Let me look."
    assert "".join(partial) == "Let me look."
    assert [e["text"] for e in events if e["type"] == "delta"] == ["Let me ", "look."]
    assert tool_calls == [
        {"id": "call_a", "type": "function", "function": {"name": "sava_test_stream_noop", "arguments": '{"x": 1}'}},
        {"id": "call_b", "type": "function", "function": {"name": "list_desks", "arguments": "{}"}},
    ]
    assert got_usage is usage


async def test_complete_synthesises_missing_tool_call_ids():
    client, _ = _streaming_client([[_chunk(tool_calls=[_frag(0, name="list_desks", arguments="{}")])]])

    async def on_event(e):
        pass

    _, tool_calls, _ = await _complete(client, "m", [], on_event, [])
    assert tool_calls[0]["id"] == "call_0"


async def test_run_agent_streams_events_in_order(monkeypatch):
    monkeypatch.setenv("SAVA_OPENROUTER_API_KEY", "test")
    first = [
        _chunk(content="Checking"),
        _chunk(tool_calls=[_frag(0, id="c1", name="sava_test_stream_noop", arguments="{}")]),
    ]
    second = [_chunk(content="All "), _chunk(content="done.")]
    client, calls = _streaming_client([first, second])
    monkeypatch.setattr(agent, "_build_client", lambda: client)
    events = []

    async def on_event(e):
        events.append(e)

    result = await run_agent("go", user=None, on_event=on_event)

    assert result["reply"] == "All done."
    assert [e["type"] for e in events] == [
        "status",
        "delta",  # "Checking" narration...
        "discard",  # ...dropped once the tool call showed up
        "tool_start",
        "action",
        "status",
        "delta",
        "delta",
    ]
    assert events[3]["tool"] == "sava_test_stream_noop"
    assert events[4]["action"]["summary"] == "ran"
    assert calls[0]["stream_options"] == {"include_usage": True}
    assert result["conversation"][-1] == {"role": "assistant", "content": "All done."}


async def test_stop_mid_reply_keeps_partial_text_and_well_formed_history(monkeypatch):
    monkeypatch.setenv("SAVA_OPENROUTER_API_KEY", "test")

    class _Hanging:
        """Yields two words then blocks until cancelled, like a stopped stream."""

        def __init__(self):
            self.n = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            self.n += 1
            if self.n <= 2:
                return _chunk(content=["Partial ", "answer"][self.n - 1])
            await asyncio.Event().wait()

    class _Completions:
        async def create(self, **kwargs):
            return _Hanging()

    monkeypatch.setattr(
        agent, "_build_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    )
    seen = asyncio.Event()

    async def on_event(e):
        if e.get("text") == "answer":
            seen.set()

    task = asyncio.create_task(run_agent("go", user=None, on_event=on_event))
    await seen.wait()
    task.cancel()
    result = await task  # the agent absorbs the cancellation and returns normally

    assert result["reply"] == "Partial answer"
    assert result["pending"] is None
    assert result["conversation"][-1] == {"role": "assistant", "content": "Partial answer"}


async def test_stop_while_tool_runs_closes_the_dangling_call(monkeypatch):
    monkeypatch.setenv("SAVA_OPENROUTER_API_KEY", "test")
    started = asyncio.Event()

    @tool(name="sava_test_slow_tool", description="slow", parameters={"type": "object", "properties": {}})
    async def _slow(args, ctx):
        started.set()
        await asyncio.Event().wait()
        return ToolResult(ok=True, summary="never", for_model="never")

    client, _ = _streaming_client(
        [[_chunk(tool_calls=[_frag(0, id="c1", name="sava_test_slow_tool", arguments="{}")])]]
    )
    monkeypatch.setattr(agent, "_build_client", lambda: client)

    async def on_event(e):
        pass

    task = asyncio.create_task(run_agent("go", user=None, on_event=on_event))
    await started.wait()
    task.cancel()
    result = await task

    tool_msgs = [m for m in result["conversation"] if m["role"] == "tool"]
    assert tool_msgs and "stopped" in tool_msgs[0]["content"]
    assert result["actions"][-1]["summary"].startswith("Not run")
    assert result["reply"] == ""
