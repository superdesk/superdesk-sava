"""SAVA HTTP endpoints (new async superdesk.core.web framework)."""

import logging

from pydantic import BaseModel
from superdesk.core.web import EndpointGroup
from superdesk.core.types import Request, Response

from . import conversations
from .agent import _build_client, run_agent

logger = logging.getLogger(__name__)

sava_endpoints = EndpointGroup("sava", __name__)


class ConversationArgs(BaseModel):
    conversation_id: str


async def _payload(request: Request) -> dict:
    try:
        payload = await request.get_json()
    except Exception:  # noqa: BLE001 - a malformed/non-JSON body should not 500
        payload = None
    return payload if isinstance(payload, dict) else {}


def _decision_label(decision: dict) -> str:
    label = decision.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return "Confirmed" if decision.get("approved") else "Cancelled"


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
    payload = await _payload(request)
    prompt = (payload.get("prompt") or "").strip()
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else None
    conversation_id = payload.get("conversation_id")

    if not prompt and not decision:
        return Response({"reply": "Please type a command.", "actions": [], "pending": None}, 400)

    user = request.user
    conv = None
    if conversation_id:
        conv = await conversations.get_owned(conversation_id, user["_id"])
        if conv is None:
            return Response({"reply": "That conversation no longer exists.", "actions": [], "pending": None}, 404)

    try:
        result = await run_agent(prompt, user, conv.messages if conv else [], decision)
    except Exception:  # noqa: BLE001 - never leak a raw traceback to the canvas
        logger.exception("SAVA command failed")
        return Response(
            {"reply": "Something went wrong handling that. Please try again.", "actions": [], "pending": None},
            500,
        )

    body = {"reply": result["reply"], "actions": result["actions"], "pending": result["pending"]}
    if _build_client() is None:
        # Not configured: the reply explains what to set; nothing worth keeping.
        return Response({**body, "conversation_id": None, "title": None}, 200)

    new_turns = [{"role": "user", "text": prompt or _decision_label(decision or {})}]
    if result["reply"] or result["actions"]:
        new_turns.append({"role": "assistant", "text": result["reply"], "actions": result["actions"]})

    title = None
    if conv is None:
        conv = await conversations.create(user["_id"], conversations.fallback_title(prompt))
        title = await conversations.generate_title(prompt, result["reply"])
    await conversations.save_turn(conv, result["conversation"], new_turns, result["pending"], title=title)

    return Response({**body, "conversation_id": str(conv.id), "title": title or conv.title}, 200)


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
