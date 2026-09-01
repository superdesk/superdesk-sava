"""SAVA agent loop.

Runs a natural-language command through an LLM (via OpenRouter) with tool
calling, executing each tool against Superdesk as the logged-in user.

The loop is a small state machine so that confirmation-gated tools (e.g.
publish) can pause: when the model calls such a tool, the loop returns a
``pending`` action instead of executing it. The client renders an approval
card; the user's decision comes back on the next request and the loop resumes.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple

from .default_settings import get_setting, get_int_setting
from .tools import Tool, ToolContext, ToolLink, get_openai_tools, get_tool, run_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are SAVA, an assistant embedded inside Superdesk, a newsroom \
content management system for journalists. You help users act on Superdesk using \
natural language, by calling tools. Discover things at runtime — do not assume.

Core rules:
- Never invent or guess ids, headlines, dates, field values, or search results. If you \
need a value you don't have, get it with a tool or ask the user — do not fabricate one.
- If a tool returns an error, tell the user in one plain sentence what failed. Do not \
silently retry the same call, and never claim an action succeeded when a tool reported \
an error.
- When a required detail is genuinely missing, ask ONE short question. Otherwise, act.
- Datetimes you pass to tools must be ISO 8601 (e.g. 2026-07-30T09:00:00). Use the \
current date/time from your context to resolve relative dates like 'today' or 'Friday'.

Creating an article:
- If the user hasn't said which content profile to use, call list_content_profiles \
and ask them which one (e.g. Text or Basic).
- Call describe_content_profile to learn that profile's required fields, then ask the \
user for any required field they haven't already provided.
- Then call create_article with `profile` and a `fields` object.

Finding things:
- Use find_articles / find_my_articles / find_desk_items to search. Pass desk and author \
names directly — the tools resolve them. For relative dates use `date_filter` \
(today / this_week / this_month) rather than guessing calendar dates.
- To act on an existing article (edit, move, spike, publish) you need its id. If you \
don't already have it from earlier in the conversation, find it first.
- Items returned by search and list tools are shown to the user as cards (headline, \
state, desk, open link). Do not repeat that list in your reply: give a one-line summary \
(how many, anything notable) and offer the obvious next step.

Editing & workflow:
- update_article changes fields; move_article sends it to a desk; spike removes an item \
from the workflow and unspike restores it. Articles, planning items and events can all be \
spiked and unspiked — use spike_article / spike_planning_item / spike_event, or \
unspike_article / unspike_planning_item / unspike_event, for the matching item type. \
Publishing and spiking are confirmed by the platform, so just call the tool — do not ask \
for confirmation yourself.

Planning, events & assignments:
- Requirements for events, planning items and coverages are configured per-instance and \
can change. Before creating one, call describe_planning_profile (event / planning / \
coverage) to learn which fields are required, and ask the user for any required field \
they haven't provided — do not assume a fixed set.
- Pass fields the tool doesn't have a named parameter for via the `fields` object (e.g. \
{"language": "en"}).
- Use create_planning_item / add_coverage / search_planning for planning; coverage types \
come from list_coverage_types.
- Use create_event / update_event / search_events for calendar events, \
link_event_to_planning to connect an event to a planning item, and post_event / \
unpost_event to publish or withdraw an event.
- Events and planning items have workflow actions: cancel_event / cancel_planning_item \
(cancel it and its planning/coverages), postpone_event / postpone_planning_item, \
reschedule_event / reschedule_planning_item, and update_event_time (change an event's \
start/end). Cancelling and unposting are confirmed by the platform. Some instances \
require a reason for these — pass one from the user when they give it.
- Use list_my_assignments for the user's assignments.

General:
- Only take actions the user asked for. If a request needs a capability you have no tool \
for, say so briefly instead of guessing.
- Keep replies short and factual. Refer to items by their headline/slugline, not their \
raw id (a link to open the item is shown to the user automatically)."""


def _date_context() -> str:
    """Current date/time line, attached to the user's turn rather than the system prompt.

    Deliberately kept out of the system+tools prefix: a per-request timestamp in that
    prefix changes it on every call, which busts a self-hosted model server's prompt
    cache and forces it to re-process every tool schema from scratch (very slow on CPU).
    Putting the volatile bit at the end of the (trailing) user turn keeps the big prefix
    stable and cacheable.
    """
    from superdesk.utc import utcnow

    from .tools.lookups import instance_timezone

    now = utcnow()
    tz = instance_timezone()
    return (
        f"Context: the current date/time is {now.isoformat()} (UTC); the instance "
        f"timezone is {tz}. Use these to compute relative dates like 'today' or 'Friday'."
    )


_CLIENT: Dict[Tuple[str, str], Any] = {}


def _build_client():
    """The AsyncOpenAI client for the configured endpoint, or None if unconfigured.

    Cached per (key, base URL) so the underlying HTTP connection pool is reused
    across requests instead of being rebuilt, and re-created if the settings change.
    """
    api_key = get_setting("SAVA_OPENROUTER_API_KEY")
    if not api_key:
        return None
    base_url = get_setting("SAVA_OPENROUTER_BASE_URL")
    cache_key = (api_key, base_url)
    if cache_key not in _CLIENT:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.error("SAVA: the 'openai' package is not installed.")
            return None
        _CLIENT.clear()
        _CLIENT[cache_key] = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return _CLIENT[cache_key]


# Some models (e.g. gpt-oss via its "harmony" format) leak a channel marker like
# "final"/"analysis" glued to the start of the reply ("finalCreated ..."). Strip it
# only when immediately followed by an uppercase letter, so words like "Finally" survive.
_CHANNEL_PREFIX = re.compile(r"^(final|analysis|assistant|commentary)\s*(?=[A-Z])")


def _clean_reply(text: str) -> str:
    if not text:
        return text
    return _CHANNEL_PREFIX.sub("", text.strip())


def _sanitize_message(m: Any) -> Optional[Dict[str, Any]]:
    """Rebuild one client-supplied history message from known fields only.

    The client round-trips the conversation verbatim, so it is untrusted input:
    only user/assistant/tool roles are accepted (a client-supplied ``system``
    message would override the prompt), and each message is reduced to the fields
    the model API expects so nothing else rides along.
    """
    if not isinstance(m, dict):
        return None
    role = m.get("role")
    content = m.get("content")
    if role not in ("user", "assistant", "tool") or not isinstance(content, (str, type(None))):
        return None
    clean: Dict[str, Any] = {"role": role, "content": content or ""}

    if role == "tool":
        tool_call_id = m.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            return None
        clean["tool_call_id"] = tool_call_id
        return clean

    if role == "assistant" and m.get("tool_calls") is not None:
        calls = []
        for tc in m["tool_calls"] if isinstance(m["tool_calls"], list) else []:
            fn = tc.get("function") if isinstance(tc, dict) else None
            if not isinstance(fn, dict) or not isinstance(tc.get("id"), str) or not isinstance(fn.get("name"), str):
                return None
            arguments = fn.get("arguments")
            calls.append(
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": fn["name"], "arguments": arguments if isinstance(arguments, str) else "{}"},
                }
            )
        if calls:
            clean["tool_calls"] = calls
    return clean


def _sanitize_history(history: Any) -> List[Dict[str, Any]]:
    if not isinstance(history, list):
        return []
    cleaned = [_sanitize_message(m) for m in history]
    return [m for m in cleaned if m is not None]


def _unresolved_tool_calls(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tool calls on the trailing assistant message that have no tool result yet."""
    if not messages:
        return []
    trailing = messages[-1]
    if trailing.get("role") != "assistant" or not trailing.get("tool_calls"):
        return []
    resolved_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    return [tc for tc in trailing["tool_calls"] if tc["id"] not in resolved_ids]


def _close_dangling_tool_calls(messages: List[Dict[str, Any]], actions: List[Dict[str, Any]], reason: str) -> None:
    """Append a synthetic result for every unresolved tool call on the trailing
    assistant message.

    The model API rejects a conversation where an assistant tool call is not
    followed by its tool result, so leaving one dangling (step limit hit, or the
    user typed a new message instead of answering a confirmation) would break every
    later turn. Closing them keeps the history well-formed.
    """
    for tc in _unresolved_tool_calls(messages):
        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": f"Not executed: {reason}"})
        actions.append(
            {"tool": tc["function"]["name"], "ok": False, "summary": f"Not run ({reason})", "detail": None, "links": []}
        )


def _trim_history(conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bound conversation length, trimming at a user-message boundary so tool
    call/result pairs at the tail are never split."""
    max_messages = get_int_setting("SAVA_MAX_HISTORY_MESSAGES")
    trimmed = conversation[-max_messages:]
    while trimmed and trimmed[0].get("role") != "user":
        trimmed = trimmed[1:]
    return trimmed


def _build_pending(tc_id: str, t: Tool, args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Describe a confirmation-gated action for the client's approval card."""
    links = []
    if args.get("article_id"):
        links = [ctx.link_to_item(str(args["article_id"])).to_dict()]
    elif args.get("event_id") or args.get("planning_id"):
        links = [ToolLink(label="Open planning", route="/planning").to_dict()]
    return {
        "id": tc_id,
        "tool": t.name,
        "title": t.confirm_title or f"Run {t.name}?",
        "confirm_label": t.confirm_label,
        "cancel_label": "Cancel",
        "links": links,
    }


EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


async def _emit(on_event: Optional[EventHandler], event: Dict[str, Any]) -> None:
    if on_event is not None:
        await on_event(event)


async def _resolve_tool_calls(
    messages: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
    ctx: ToolContext,
    approved: Set[str],
    denied: Set[str],
    on_event: Optional[EventHandler] = None,
) -> Optional[Dict[str, Any]]:
    """Execute any unresolved tool_calls on the trailing assistant message.

    Returns a ``pending`` dict if a confirmation-gated call is awaiting a decision
    (and stops there), otherwise None once all calls are resolved.
    """
    for tc in _unresolved_tool_calls(messages):
        tc_id = tc["id"]
        name = tc["function"]["name"]
        try:
            args = json.loads(tc["function"].get("arguments") or "{}")
        except (TypeError, ValueError):
            args = {}

        t = get_tool(name)

        if t is not None and t.requires_confirmation and tc_id not in approved and tc_id not in denied:
            return _build_pending(tc_id, t, args, ctx)

        if tc_id in denied:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": "The user declined to perform this action.",
                }
            )
            actions.append({"tool": name, "ok": False, "summary": "Cancelled by user", "detail": None, "links": []})
            await _emit(on_event, {"type": "action", "action": actions[-1]})
            continue

        await _emit(on_event, {"type": "tool_start", "tool": name})
        result = await run_tool(name, args, ctx)
        messages.append({"role": "tool", "tool_call_id": tc_id, "content": result.for_model})
        actions.append(result.action_dict(name))
        await _emit(on_event, {"type": "action", "action": actions[-1]})

    return None


def _add_usage(total: Dict[str, int], usage: Any) -> None:
    for key in total:
        value = getattr(usage, key, None)
        if isinstance(value, int):
            total[key] += value


def _tool_call_dict(tc: Any) -> Dict[str, Any]:
    return {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}


async def _complete(
    client: Any,
    model: str,
    messages: List[Dict[str, Any]],
    on_event: Optional[EventHandler],
    partial: List[str],
) -> Tuple[str, List[Dict[str, Any]], Any]:
    """One model call. Returns ``(content, tool_calls, usage)`` with tool calls in
    the plain dict shape the history stores.

    With an event handler the call is streamed: content chunks are appended to
    ``partial`` (so a stopped turn can keep what arrived) and emitted as ``delta``
    events, while tool-call fragments are reassembled by index.
    """
    common = {
        "model": model,
        "messages": messages,
        "tools": get_openai_tools(),
        "tool_choice": "auto",
        "temperature": 0,
    }
    if on_event is None:
        response = await client.chat.completions.create(**common)
        message = response.choices[0].message
        calls = [_tool_call_dict(tc) for tc in (message.tool_calls or [])]
        return message.content or "", calls, getattr(response, "usage", None)

    stream = await client.chat.completions.create(**common, stream=True, stream_options={"include_usage": True})
    slots: Dict[int, Dict[str, Any]] = {}
    usage = None
    async for chunk in stream:
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        if delta.content:
            partial.append(delta.content)
            await on_event({"type": "delta", "text": delta.content})
        for fragment in delta.tool_calls or []:
            slot = slots.setdefault(
                fragment.index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
            )
            if fragment.id:
                slot["id"] = fragment.id
            fn = getattr(fragment, "function", None)
            if fn is not None:
                if fn.name:
                    slot["function"]["name"] = fn.name
                if fn.arguments:
                    slot["function"]["arguments"] += fn.arguments
    ordered = [slots[i] for i in sorted(slots)]
    for n, call in enumerate(ordered):
        call["id"] = call["id"] or f"call_{n}"
    return "".join(partial), ordered, usage


async def run_agent(
    prompt: str,
    user: Optional[Dict[str, Any]],
    history: Optional[List[Dict[str, Any]]] = None,
    decision: Optional[Dict[str, Any]] = None,
    on_event: Optional[EventHandler] = None,
) -> Dict[str, Any]:
    """Run one turn. Returns
    ``{"reply", "actions", "conversation", "pending"}`` where ``pending`` is a
    confirmation card the client must resolve (or None).

    With ``on_event`` the turn streams progress (``status``, ``tool_start``,
    ``action``, ``delta``, ``discard``) and the model is called in streaming mode.
    If the task is cancelled mid-turn (the client pressed Stop / disconnected),
    the history is left well-formed and whatever reply text arrived is kept.
    """
    prior = _sanitize_history(history)
    ctx = ToolContext(user=user)
    model = get_setting("SAVA_MODEL")
    max_steps = get_int_setting("SAVA_MAX_STEPS")
    actions: List[Dict[str, Any]] = []
    started = time.monotonic()
    steps = 0
    usage = {"prompt_tokens": 0, "completion_tokens": 0}

    def finish(
        reply: str, messages: List[Dict[str, Any]], pending: Optional[Dict[str, Any]] = None, outcome: str = "ok"
    ):
        # One structured line per turn: the data behind any cost/latency discussion.
        logger.info(
            "SAVA turn: model=%s outcome=%s steps=%d tools=%s prompt_tokens=%d completion_tokens=%d ms=%d user=%s",
            model,
            outcome,
            steps,
            ",".join(a["tool"] for a in actions) or "-",
            usage["prompt_tokens"],
            usage["completion_tokens"],
            int((time.monotonic() - started) * 1000),
            (user or {}).get("_id", "-"),
        )
        return {"reply": reply, "actions": actions, "conversation": _trim_history(messages), "pending": pending}

    client = _build_client()
    if client is None:
        return finish(
            "SAVA is not configured. Set SAVA_OPENROUTER_API_KEY (and optionally "
            "SAVA_MODEL) in the server environment.",
            prior,
            outcome="unconfigured",
        )

    approved: Set[str] = set()
    denied: Set[str] = set()
    if isinstance(decision, dict) and isinstance(decision.get("id"), str):
        (approved if decision.get("approved") else denied).add(decision["id"])

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(prior)
    if prompt:
        # A new message supersedes any confirmation still waiting on the tail.
        _close_dangling_tool_calls(messages, actions, "the user sent a new message instead of a decision")
        messages.append({"role": "user", "content": f"{_date_context()}\n\n{prompt}"})

    partial: List[str] = []
    try:
        for _ in range(max_steps):
            # 1. Resolve any pending tool_calls on the trailing assistant message
            #    (handles both fresh turns and resumes after an approval).
            pending = await _resolve_tool_calls(messages, actions, ctx, approved, denied, on_event)
            if pending is not None:
                return finish("", messages[1:], pending=pending, outcome="pending")

            # 2. Ask the model what to do next.
            steps += 1
            partial = []
            await _emit(on_event, {"type": "status", "text": "Thinking…"})
            try:
                content, tool_calls, step_usage = await _complete(client, model, messages, on_event, partial)
            except Exception as exc:  # noqa: BLE001 - report model/transport failures
                logger.exception("SAVA model call failed")
                return finish(f"The AI request failed: {exc}", messages[1:], outcome="model_error")

            _add_usage(usage, step_usage)

            if not tool_calls:
                reply = _clean_reply(content) or "Done."
                messages.append({"role": "assistant", "content": reply})
                return finish(reply, messages[1:])

            # Any text alongside tool calls is narration, not the reply: tell a
            # streaming client to drop what it showed, and don't keep it for Stop.
            if content:
                await _emit(on_event, {"type": "discard"})
            partial = []

            # Append the assistant's tool-call message; the loop resolves it on the
            # next iteration (step 1).
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        _close_dangling_tool_calls(messages, actions, "step limit reached")
        return finish(
            "I reached the step limit before fully finishing. Here is what I did.", messages[1:], outcome="step_limit"
        )
    except asyncio.CancelledError:
        # Stopped by the user (the streaming client went away). Keep the history
        # well-formed and whatever reply text had arrived; the caller persists it.
        _close_dangling_tool_calls(messages, actions, "stopped by the user")
        reply = _clean_reply("".join(partial))
        if reply:
            messages.append({"role": "assistant", "content": reply})
        return finish(reply, messages[1:], outcome="stopped")
