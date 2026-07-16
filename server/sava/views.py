"""SAVA HTTP endpoints (new async superdesk.core.web framework)."""

import logging

from superdesk.core.web import EndpointGroup
from superdesk.core.types import Request, Response

from .agent import run_agent

logger = logging.getLogger(__name__)

sava_endpoints = EndpointGroup("sava", __name__)


@sava_endpoints.endpoint("sava/command", methods=["POST"])
async def sava_command(request: Request) -> Response:
    """Handle a natural-language command from the SAVA canvas.

    Body: ``{"prompt": "<text>"}``
    Returns: ``{"reply": str, "actions": [{tool, summary, ok, detail}]}``
    """
    payload = await request.get_json()
    prompt = ((payload or {}).get("prompt") or "").strip()

    if not prompt:
        return Response({"reply": "Please type a command.", "actions": []}, 400)

    result = await run_agent(prompt, request.user)
    return Response(result, 200)
