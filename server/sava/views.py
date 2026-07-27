"""SAVA HTTP endpoints (new async superdesk.core.web framework)."""

import logging

from superdesk.core.web import EndpointGroup
from superdesk.core.types import Request, Response

from .agent import run_agent

logger = logging.getLogger(__name__)

sava_endpoints = EndpointGroup("sava", __name__)


@sava_endpoints.endpoint("sava/command", methods=["POST"])
async def sava_command(request: Request) -> Response:
    """Handle a turn from the SAVA canvas.

    Body:
        {
          "prompt": "<text>",              # a new command (omit on a pure approval turn)
          "conversation": [...],           # prior history the client round-trips
          "decision": {"id": "..", "approved": true|false}   # optional: resolve a pending action
        }

    Returns:
        {
          "reply": str,
          "actions": [{tool, ok, summary, detail, links}],
          "conversation": [...],
          "pending": null | {id, tool, title, confirm_label, cancel_label, links}
        }

    The server is stateless: the client round-trips ``conversation`` (so the agent
    remembers prior turns) and ``pending`` confirmations resolve via ``decision``.
    """
    try:
        payload = await request.get_json()
    except Exception:  # noqa: BLE001 - a malformed/non-JSON body should not 500
        payload = None
    if not isinstance(payload, dict):
        payload = {}

    prompt = (payload.get("prompt") or "").strip()
    history = payload.get("conversation")
    decision = payload.get("decision")

    if not prompt and not decision:
        return Response(
            {"reply": "Please type a command.", "actions": [], "conversation": history or [], "pending": None},
            400,
        )

    try:
        result = await run_agent(prompt, request.user, history, decision)
    except Exception:  # noqa: BLE001 - never leak a raw traceback to the canvas
        logger.exception("SAVA command failed")
        return Response(
            {
                "reply": "Something went wrong handling that. Please try again.",
                "actions": [],
                "conversation": history or [],
                "pending": None,
            },
            500,
        )
    return Response(result, 200)
