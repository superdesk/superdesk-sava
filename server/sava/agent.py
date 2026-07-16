"""SAVA agent loop.

Runs a natural-language command through an LLM (via OpenRouter) with tool
calling, executing each tool against Superdesk as the logged-in user.

The loop is a small state machine so that confirmation-gated tools (e.g.
publish) can pause: when the model calls such a tool, the loop returns a
``pending`` action instead of executing it. The client renders an approval
card; the user's decision comes back on the next request and the loop resumes.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from .default_settings import get_setting, get_int_setting
from .tools import Tool, ToolContext, get_openai_tools, get_tool, run_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are SAVA, an assistant embedded inside Superdesk, a newsroom \
content management system for journalists. You help users act on Superdesk using \
natural language, by calling tools. Discover things at runtime — do not assume.

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

Editing & workflow:
- update_article changes fields; move_article sends it to a desk; spike_article removes \
it. Publishing and spiking are confirmed by the platform, so just call the tool — do not \
ask for confirmation yourself.

Planning & assignments:
- Use create_planning_item / add_coverage / search_planning for planning; coverage types \
come from list_coverage_types. Use list_my_assignments for the user's assignments.

General:
- Only take actions the user asked for. If a request needs a capability you have no tool \
for, say so briefly instead of guessing.
- Keep replies short and factual. Refer to items by their headline/slugline, not their \
raw id (a link to open the item is shown to the user automatically)."""


def _build_client():
    """Create an AsyncOpenAI client pointed at OpenRouter, or None if unconfigured."""
    api_key = get_setting("SAVA_OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.error("SAVA: the 'openai' package is not installed.")
        return None
    return AsyncOpenAI(api_key=api_key, base_url=get_setting("SAVA_OPENROUTER_BASE_URL"))


# Some models (e.g. gpt-oss via its "harmony" format) leak a channel marker like
# "final"/"analysis" glued to the start of the reply ("finalCreated ..."). Strip it
# only when immediately followed by an uppercase letter, so words like "Finally" survive.
_CHANNEL_PREFIX = re.compile(r"^(final|analysis|assistant|commentary)\s*(?=[A-Z])")


def _clean_reply(text: str) -> str:
    if not text:
        return text
    return _CHANNEL_PREFIX.sub("", text.strip())


def _sanitize_history(history: Any) -> List[Dict[str, Any]]:
    if not isinstance(history, list):
        return []
    return [m for m in history if isinstance(m, dict) and m.get("role")]


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
    article_id = args.get("article_id")
    if article_id:
        links = [ctx.link_to_item(str(article_id)).to_dict()]
    return {
        "id": tc_id,
        "tool": t.name,
        "title": t.confirm_title or f"Run {t.name}?",
        "confirm_label": t.confirm_label,
        "cancel_label": "Cancel",
        "links": links,
    }


async def _resolve_tool_calls(
    messages: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
    ctx: ToolContext,
    approved: Set[str],
    denied: Set[str],
) -> Optional[Dict[str, Any]]:
    """Execute any unresolved tool_calls on the trailing assistant message.

    Returns a ``pending`` dict if a confirmation-gated call is awaiting a decision
    (and stops there), otherwise None once all calls are resolved.
    """
    if not messages:
        return None
    trailing = messages[-1]
    if trailing.get("role") != "assistant" or not trailing.get("tool_calls"):
        return None

    resolved_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}

    for tc in trailing["tool_calls"]:
        tc_id = tc["id"]
        if tc_id in resolved_ids:
            continue

        name = tc["function"]["name"]
        try:
            args = json.loads(tc["function"].get("arguments") or "{}")
        except (TypeError, ValueError):
            args = {}

        t = get_tool(name)

        if t is not None and t.requires_confirmation and tc_id not in approved and tc_id not in denied:
            return _build_pending(tc_id, t, args, ctx)

        if tc_id in denied:
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": "The user declined to perform this action.",
            })
            actions.append({"tool": name, "ok": False, "summary": "Cancelled by user", "detail": None, "links": []})
            continue

        result = await run_tool(name, args, ctx)
        messages.append({"role": "tool", "tool_call_id": tc_id, "content": result.for_model})
        actions.append(result.action_dict(name))

    return None


async def run_agent(
    prompt: str,
    user: Optional[Dict[str, Any]],
    history: Optional[List[Dict[str, Any]]] = None,
    decision: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run one turn. Returns
    ``{"reply", "actions", "conversation", "pending"}`` where ``pending`` is a
    confirmation card the client must resolve (or None)."""
    prior = _sanitize_history(history)
    ctx = ToolContext(user=user)

    client = _build_client()
    if client is None:
        return {
            "reply": (
                "SAVA is not configured. Set SAVA_OPENROUTER_API_KEY (and optionally "
                "SAVA_MODEL) in the server environment."
            ),
            "actions": [],
            "conversation": prior,
            "pending": None,
        }

    model = get_setting("SAVA_MODEL")
    max_steps = get_int_setting("SAVA_MAX_STEPS")

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(prior)
    if prompt:
        messages.append({"role": "user", "content": prompt})

    approved: Set[str] = set()
    denied: Set[str] = set()
    if isinstance(decision, dict) and decision.get("id"):
        (approved if decision.get("approved") else denied).add(decision["id"])

    actions: List[Dict[str, Any]] = []
    reply = "Done."

    for _ in range(max_steps):
        # 1. Resolve any pending tool_calls on the trailing assistant message
        #    (handles both fresh turns and resumes after an approval).
        pending = await _resolve_tool_calls(messages, actions, ctx, approved, denied)
        if pending is not None:
            return {
                "reply": "",
                "actions": actions,
                "conversation": _trim_history(messages[1:]),
                "pending": pending,
            }

        # 2. Ask the model what to do next.
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=get_openai_tools(),
                tool_choice="auto",
                temperature=0,
            )
        except Exception as exc:  # noqa: BLE001 - report model/transport failures
            logger.exception("SAVA model call failed")
            return {
                "reply": f"The AI request failed: {exc}",
                "actions": actions,
                "conversation": _trim_history(messages[1:]),
                "pending": None,
            }

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            reply = _clean_reply(message.content or "") or "Done."
            messages.append({"role": "assistant", "content": reply})
            return {
                "reply": reply,
                "actions": actions,
                "conversation": _trim_history(messages[1:]),
                "pending": None,
            }

        # Append the assistant's tool-call message; the loop resolves it on the
        # next iteration (step 1).
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ],
        })

    return {
        "reply": "I reached the step limit before fully finishing. Here is what I did.",
        "actions": actions,
        "conversation": _trim_history(messages[1:]),
        "pending": None,
    }
