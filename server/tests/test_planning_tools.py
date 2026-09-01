"""Planning tools reject bad datetimes before touching the resource layer."""

from sava.tools import run_tool
from sava.tools.base import ToolContext


async def test_create_planning_item_rejects_bad_planning_date():
    res = await run_tool("create_planning_item", {"slugline": "x", "planning_date": "next tuesday"}, ToolContext())
    assert res.ok is False
    assert "planning_date" in res.for_model


async def test_create_planning_item_rejects_bad_coverage_schedule():
    args = {"slugline": "x", "coverages": [{"g2_content_type": "text", "scheduled": "tomorrow 9am"}]}
    res = await run_tool("create_planning_item", args, ToolContext())
    assert res.ok is False
    assert "scheduled" in res.for_model


async def test_add_coverage_rejects_bad_schedule():
    res = await run_tool(
        "add_coverage", {"planning_id": "p1", "coverage_type": "text", "scheduled": "soon"}, ToolContext()
    )
    assert res.ok is False
    assert "scheduled" in res.for_model
