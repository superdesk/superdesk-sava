"""SAVA HTTP endpoints (new async superdesk.core.web framework)."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel
from quart import Response as QuartResponse
from superdesk.core.web import EndpointGroup
from superdesk.core.types import Request, Response
from superdesk.utils import get_cors_headers

from . import conversations
from .agent import EventHandler, _build_client, run_agent

logger = logging.getLogger(__name__)

sava_endpoints = EndpointGroup("sava", __name__)


class ConversationArgs(BaseModel):
    conversation_id: str


async def _payload(request: Request) -> dict:
    try:
        payload = await request.get_json(force=True)  # parse even without a JSON content type
    except Exception:  # noqa: BLE001 - a malformed/non-JSON body should not 500
        payload = None
    return payload if isinstance(payload, dict) else {}


def _decision_label(decision: dict) -> str:
    label = decision.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return "Confirmed" if decision.get("approved") else "Cancelled"


async def _run_turn(user: dict, payload: dict, on_event: Optional[EventHandler] = None) -> Tuple[Dict[str, Any], int]:
    """Run one turn for ``user`` and persist it. Returns ``(body, status)``.

    Shared by the JSON endpoint and the streaming one; ``on_event`` receives the
    agent's progress events when streaming.
    """
    prompt = (payload.get("prompt") or "").strip()
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else None
    conversation_id = payload.get("conversation_id")

    if not prompt and not decision:
        return {"reply": "Please type a command.", "actions": [], "pending": None}, 400

    conv = None
    if conversation_id:
        conv = await conversations.get_owned(conversation_id, user["_id"])
        if conv is None:
            return {"reply": "That conversation no longer exists.", "actions": [], "pending": None}, 404

    try:
        result = await run_agent(prompt, user, conv.messages if conv else [], decision, on_event)
    except Exception:  # noqa: BLE001 - never leak a raw traceback to the canvas
        logger.exception("SAVA command failed")
        return {"reply": "Something went wrong handling that. Please try again.", "actions": [], "pending": None}, 500

    body: Dict[str, Any] = {"reply": result["reply"], "actions": result["actions"], "pending": result["pending"]}
    if _build_client() is None:
        # Not configured: the reply explains what to set; nothing worth keeping.
        return {**body, "conversation_id": None, "title": None}, 200

    new_turns = [{"role": "user", "text": prompt or _decision_label(decision or {})}]
    if result["reply"] or result["actions"]:
        new_turns.append({"role": "assistant", "text": result["reply"], "actions": result["actions"]})

    title = None
    if conv is None:
        conv = await conversations.create(user["_id"], conversations.fallback_title(prompt))
        title = await conversations.generate_title(prompt, result["reply"])
    await conversations.save_turn(conv, result["conversation"], new_turns, result["pending"], title=title)

    return {**body, "conversation_id": str(conv.id), "title": title or conv.title}, 200


@sava_endpoints.endpoint("sava/command", methods=["POST"])
async def sava_command(request: Request) -> Response:
    """Handle a turn from the SAVA canvas.

    Body:
        {
          "prompt": "<text>",                  # a new command (omit on a pure approval turn)
          "conversation_id": "<id>",           # omit to start a new conversation
          "decision": {"id": "..", "approved": true|false, "label": ".."}   # resolve a pending action
        }

    Returns:
        {
          "reply": str,
          "actions": [{tool, ok, summary, detail, links}],
          "pending": null | {id, tool, title, confirm_label, cancel_label, links},
          "conversation_id": str | null,
          "title": str | null
        }

    History lives server-side, scoped to the logged-in user: the first turn creates
    the conversation (and gives it a title), later turns continue it by id.
    """
    body, status = await _run_turn(request.user, await _payload(request))
    return Response(body, status)


@sava_endpoints.endpoint("sava/command/stream", methods=["POST"])
async def sava_command_stream(request: Request):
    """Same as ``sava/command`` but streamed as server-sent events.

    Each line is ``data: <json>`` with a ``type`` of ``status``, ``tool_start``,
    ``action``, ``delta`` (reply text), ``discard`` (drop the text shown so far),
    ``done`` (the full ``sava/command`` body) or ``error``. Closing the connection
    stops the turn: the agent keeps what arrived and the history stays consistent.
    """
    payload = await _payload(request)
    user = request.user
    queue: "asyncio.Queue[Optional[Dict[str, Any]]]" = asyncio.Queue()

    async def emit(event: Dict[str, Any]) -> None:
        await queue.put(event)

    async def work() -> None:
        try:
            body, status = await _run_turn(user, payload, emit)
            await queue.put({"type": "done" if status == 200 else "error", "status": status, **body})
        except Exception:  # noqa: BLE001 - never leak a raw traceback to the canvas
            logger.exception("SAVA streamed command failed")
            await queue.put({"type": "error", "status": 500, "reply": "Something went wrong handling that."})
        finally:
            await queue.put(None)

    # Runs on its own so a client disconnect cancels the turn cleanly (the agent
    # catches the cancellation, persists what it has, and the task finishes).
    task = asyncio.create_task(work())

    async def events():
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield f"data: {json.dumps(event, default=str)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    headers.update(dict(get_cors_headers("POST, OPTIONS")))
    response = QuartResponse(events(), status=200, headers=headers)
    response.timeout = None  # a turn can outlive Quart's default body timeout
    return response


@sava_endpoints.endpoint("sava/conversations", methods=["GET"])
async def list_conversations(request: Request) -> Response:
    """The logged-in user's conversations, most recently updated first."""
    return Response({"_items": await conversations.list_for_user(request.user["_id"])}, 200)


@sava_endpoints.endpoint("sava/conversations/<string:conversation_id>", methods=["GET"])
async def get_conversation(args: ConversationArgs, params: None, request: Request) -> Response:
    conv = await conversations.get_owned(args.conversation_id, request.user["_id"])
    if conv is None:
        return Response({"message": "Conversation not found"}, 404)
    return Response(conversations.detail(conv), 200)


@sava_endpoints.endpoint("sava/conversations/<string:conversation_id>", methods=["PATCH"])
async def rename_conversation(args: ConversationArgs, params: None, request: Request) -> Response:
    conv = await conversations.get_owned(args.conversation_id, request.user["_id"])
    if conv is None:
        return Response({"message": "Conversation not found"}, 404)
    title = conversations.fallback_title((await _payload(request)).get("title") or "")
    if title == "New chat":
        return Response({"message": "A title is required"}, 400)
    await conversations.rename(conv, title)
    return Response({"id": str(conv.id), "title": title}, 200)


@sava_endpoints.endpoint("sava/conversations/<string:conversation_id>", methods=["DELETE"])
async def delete_conversation(args: ConversationArgs, params: None, request: Request) -> Response:
    conv = await conversations.get_owned(args.conversation_id, request.user["_id"])
    if conv is None:
        return Response({"message": "Conversation not found"}, 404)
    await conversations.delete(conv)
    return Response({"id": str(conv.id)}, 200)
