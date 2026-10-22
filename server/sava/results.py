"""What a tool call gives the conversation: text for the model, and the summary, links and item cards the UI shows."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolLink:
    """A client-navigable link. The client prepends its own origin and hash router, so routes stay host-agnostic."""

    label: str
    route: str  # e.g. "/workspace/monitoring?item=<id>&action=edit"

    def to_dict(self) -> Dict[str, str]:
        return {"label": self.label, "route": self.route}


@dataclass
class ItemCard:
    """A Superdesk item the UI renders as a card. ``kind`` is article | event | planning | assignment."""

    kind: str
    id: str
    title: str
    route: str
    subtitle: Optional[str] = None
    state: Optional[str] = None
    desk: Optional[str] = None
    date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "title": self.title,
            "route": self.route,
            "subtitle": self.subtitle,
            "state": self.state,
            "desk": self.desk,
            "date": self.date,
        }


@dataclass
class ToolResult:
    """Outcome of a tool call: ``for_model`` goes back to the model, the rest to the activity log and cards."""

    ok: bool
    summary: str
    for_model: str
    detail: Optional[str] = None
    links: List[ToolLink] = field(default_factory=list)
    items: List[ItemCard] = field(default_factory=list)

    def action_dict(self, tool_name: str) -> Dict[str, Any]:
        return {
            "tool": tool_name,
            "ok": self.ok,
            "summary": self.summary,
            "detail": self.detail,
            "links": [link.to_dict() for link in self.links],
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class Pending:
    """A tool call that waits for the user's yes, with the tool's own question."""

    question: str
