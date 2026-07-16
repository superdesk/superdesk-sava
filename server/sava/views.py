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
    payload = await request.get_json()
    prompt = ((payload or {}).get("prompt") or "").strip()
    history = (payload or {}).get("conversation")
    decision = (payload or {}).get("decision")

    if not prompt and not decision:
        return Response(
            {"reply": "Please type a command.", "actions": [], "conversation": history or [], "pending": None},
            400,
        )

    result = await run_agent(prompt, request.user, history, decision)
    return Response(result, 200)
