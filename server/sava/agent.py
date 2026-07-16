"""SAVA agent loop.

Runs a natural-language command through an LLM (via OpenRouter) with tool
calling, executing each tool against Superdesk as the logged-in user, and
returns the agent's reply plus the list of actions it performed.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .default_settings import get_setting, get_int_setting
from .tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are SAVA, an assistant embedded inside Superdesk, a newsroom \
content management system for journalists.

You help users act on Superdesk using natural language. You have tools to list \
desks, create text articles, and publish articles.

Guidelines:
- Use the tools to actually perform what the user asks; do not just describe it.
- To create and then publish, first call create_article, then call \
publish_article with the article_id returned by create_article.
- Create each article only ONCE. If an earlier create_article result already \
exists in this conversation, reuse that article_id — never call create_article \
again for the same article. If a publish fails, do NOT create a new article; \
report the failure instead.
- If the user names a desk you are unsure about, use list_desks to check.
- Only take the actions the user asked for. If a request needs a capability you \
do not have a tool for, say so briefly instead of guessing.
- Keep your final reply short and factual: state what you did (and any ids)."""


def _build_client():
    """Create an AsyncOpenAI client pointed at OpenRouter, or None if unconfigured.

    Imported lazily so a missing/broken ``openai`` install never blocks the
    module (and therefore the endpoint) from loading.
    """
    api_key = get_setting("SAVA_OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.error("SAVA: the 'openai' package is not installed.")
        return None
    return AsyncOpenAI(api_key=api_key, base_url=get_setting("SAVA_OPENROUTER_BASE_URL"))


# Some models (e.g. gpt-oss via its "harmony" format) leak a channel marker
# like "final"/"analysis" glued to the start of the reply ("finalCreated ...").
# Strip it only when immediately followed by an uppercase letter, so real words
# like "Finally" are left intact.
_CHANNEL_PREFIX = re.compile(r"^(final|analysis|assistant|commentary)\s*(?=[A-Z])")


def _clean_reply(text: str) -> str:
    if not text:
        return text
    return _CHANNEL_PREFIX.sub("", text.strip())


def _record_action(result: Dict[str, Any]) -> Dict[str, Any]:
    """Project a tool result down to the shape the client renders."""
    return {
        "tool": result.get("tool", ""),
        "summary": result.get("summary", ""),
        "ok": bool(result.get("ok")),
        "detail": result.get("detail"),
    }


def _trim_history(conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bound conversation length, trimming at a user-message boundary.

    Keeping the last N messages could otherwise start the history on an
    orphaned ``tool`` / ``assistant`` message (a tool result must follow the
    assistant tool-call that produced it), which the model API rejects. So we
    take the last N, then drop any leading messages until the first is a
    ``user`` message.
    """
    max_messages = get_int_setting("SAVA_MAX_HISTORY_MESSAGES")
    trimmed = conversation[-max_messages:]
    while trimmed and trimmed[0].get("role") != "user":
        trimmed = trimmed[1:]
    return trimmed


def _sanitize_history(history: Any) -> List[Dict[str, Any]]:
    """Accept only a list of message dicts; ignore anything malformed."""
    if not isinstance(history, list):
        return []
    return [m for m in history if isinstance(m, dict) and m.get("role")]


async def run_agent(
    prompt: str,
    user: Optional[Dict[str, Any]],
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run one command end-to-end.

    ``history`` is the prior conversation (everything after the system prompt)
    that the client echoed back. Returns
    ``{"reply": str, "actions": [...], "conversation": [...]}`` where
    ``conversation`` is the updated history to send back on the next turn.
    """
    prior = _sanitize_history(history)

    client = _build_client()
    if client is None:
        return {
            "reply": (
                "SAVA is not configured. Set SAVA_OPENROUTER_API_KEY (and optionally "
                "SAVA_MODEL) in the server environment."
            ),
            "actions": [],
            "conversation": prior,
        }

    model = get_setting("SAVA_MODEL")
    max_steps = get_int_setting("SAVA_MAX_STEPS")

    # The system prompt is prepended fresh each turn and is never part of the
    # returned conversation.
    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(prior)
    messages.append({"role": "user", "content": prompt})

    actions: List[Dict[str, Any]] = []
    reply = "Done."

    for _ in range(max_steps):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0,
            )
        except Exception as exc:  # noqa: BLE001 - report model/transport failures
            logger.exception("SAVA model call failed")
            return {
                "reply": f"The AI request failed: {exc}",
                "actions": actions,
                # messages always ends on a complete turn boundary here, so it
                # is safe to hand back as the next turn's history.
                "conversation": _trim_history(messages[1:]),
            }

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            reply = _clean_reply(message.content or "") or "Done."
            messages.append({"role": "assistant", "content": reply})
            break

        # Echo the assistant's tool-call message back into the conversation.
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tool_call in tool_calls:
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except (TypeError, ValueError):
                args = {}

            result = await execute_tool(tool_call.function.name, args, user)
            actions.append(_record_action(result))

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.get("for_model", "done"),
                }
            )
    else:
        # Ran out of steps without a final (tool-call-free) reply.
        reply = "I reached the step limit before fully finishing. Here is what I did."
        messages.append({"role": "assistant", "content": reply})

    return {
        "reply": reply,
        "actions": actions,
        "conversation": _trim_history(messages[1:]),
    }
