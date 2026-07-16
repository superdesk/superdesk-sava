"""SAVA agent loop.

Runs a natural-language command through an LLM (via OpenRouter) with tool
calling, executing each tool against Superdesk as the logged-in user, and
returns the agent's reply plus the list of actions it performed.
"""

import json
import logging
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


def _record_action(result: Dict[str, Any]) -> Dict[str, Any]:
    """Project a tool result down to the shape the client renders."""
    return {
        "tool": result.get("tool", ""),
        "summary": result.get("summary", ""),
        "ok": bool(result.get("ok")),
        "detail": result.get("detail"),
    }


async def run_agent(
    prompt: str, user: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Run one command end-to-end. Returns ``{"reply": str, "actions": [...]}``."""
    client = _build_client()
    if client is None:
        return {
            "reply": (
                "SAVA is not configured. Set SAVA_OPENROUTER_API_KEY (and optionally "
                "SAVA_MODEL) in the server environment."
            ),
            "actions": [],
        }

    model = get_setting("SAVA_MODEL")
    max_steps = get_int_setting("SAVA_MAX_STEPS")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    actions: List[Dict[str, Any]] = []

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
            return {"reply": f"The AI request failed: {exc}", "actions": actions}

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            return {"reply": message.content or "Done.", "actions": actions}

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

    return {
        "reply": "I reached the step limit before fully finishing. Here is what I did.",
        "actions": actions,
    }
