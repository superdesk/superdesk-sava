"""Pure helpers in lookups: ISO-datetime validation and profile-schema splitting."""

import re
from datetime import datetime, timezone

import pytest

from sava.tools import lookups
from sava.tools.lookups import (
    DATE_FILTERS,
    DATE_FILTER_DESCRIPTION,
    MAX_RESULTS,
    contains,
    date_window,
    elastic_date_filter,
    mongo_date_filter,
    merge_extra_fields,
    parse_size,
    protected_note,
    split_required_optional,
    strip_protected_fields,
    valid_iso_datetime,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-07-30T09:00:00", True),
        ("2026-07-30T09:00:00Z", True),
        ("2026-07-30T09:00:00+02:00", True),
        ("2026-07-30", True),
        ("not a date", False),
        ("30/07/2026", False),
        ("", False),
        ("   ", False),
        (None, False),
        (12345, False),
    ],
)
def test_valid_iso_datetime(value, expected):
    assert valid_iso_datetime(value) is expected


def test_split_required_optional_partitions_by_required_flag():
    schema = {
        "headline": {"type": "string", "required": True},
        "slugline": {"type": "string", "required": False},
        "body": {"type": "string"},
        "disabled": None,
    }
    required, optional = split_required_optional(schema)
    assert required == ["headline"]
    assert set(optional) == {"slugline", "body"}
    # A null field config is skipped entirely.
    assert "disabled" not in required
    assert "disabled" not in optional


def test_split_required_optional_handles_none_schema():
    assert split_required_optional(None) == ([], [])
    assert split_required_optional({}) == ([], [])


# --- model-input guards --------------------------------------------------------


def test_parse_size_defaults_clamps_and_tolerates_junk():
    assert parse_size({}) == 25
    assert parse_size({"size": 10}) == 10
    assert parse_size({"size": "7"}) == 7
    assert parse_size({"size": 100000}) == MAX_RESULTS
    assert parse_size({"size": -5}) == 1
    assert parse_size({"size": "lots"}) == 25
    assert parse_size({"size": None}, default=5, maximum=3) == 3


def test_contains_escapes_regex_metacharacters():
    match = contains("Smith (Jr.) [test]")
    assert match["$options"] == "i"
    assert re.fullmatch(match["$regex"], "Smith (Jr.) [test]")
    assert not re.search(match["$regex"], "Smith Jr test")


@pytest.mark.parametrize("key", ["_id", "_etag", "state", "task", "lock_user", "original_creator", "type"])
def test_strip_protected_fields_drops_system_keys(key):
    clean, dropped = strip_protected_fields({key: "x", "headline": "ok"})
    assert clean == {"headline": "ok"}
    assert dropped == [key]


def test_strip_protected_fields_drops_none_silently_and_non_dicts():
    assert strip_protected_fields({"headline": None, "slugline": "s"}) == ({"slugline": "s"}, [])
    assert strip_protected_fields("nope") == ({}, [])
    assert strip_protected_fields(None) == ({}, [])


def test_merge_extra_fields_does_not_override_and_reports_dropped():
    item = {"slugline": "set-by-tool"}
    dropped = merge_extra_fields(item, {"slugline": "model", "language": "en", "state": "published"})
    assert item == {"slugline": "set-by-tool", "language": "en"}
    assert dropped == ["state"]
    assert merge_extra_fields(item, None) == []


def test_protected_note():
    assert protected_note([]) == ""
    assert "state, task" in protected_note(["state", "task"])


# --- date filters ---------------------------------------------------------------

# Saturday 2026-08-01 23:30 UTC == Sunday 2026-08-02 01:30 in Prague (CEST, UTC+2):
# day/week/month boundaries must be computed in the instance timezone, not UTC.
_NOW = datetime(2026, 8, 1, 23, 30, tzinfo=timezone.utc)


@pytest.fixture
def prague(monkeypatch):
    monkeypatch.setattr(lookups, "instance_timezone", lambda: "Europe/Prague")


def _utc(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=timezone.utc)


def test_date_window_today_uses_instance_timezone(prague):
    start, end = date_window("today", _NOW)
    assert (start, end) == (_utc(2026, 8, 1, 22), _utc(2026, 8, 2, 22))  # Sun 00:00-24:00 Prague


def test_date_window_this_week_is_monday_to_sunday(prague):
    start, end = date_window("this_week", _NOW)
    assert start == _utc(2026, 7, 26, 22)  # Mon 27 Jul 00:00 Prague
    assert end == _utc(2026, 8, 2, 22)  # Mon 3 Aug 00:00 Prague (exclusive)


def test_date_window_this_month_is_calendar_month(prague):
    start, end = date_window("this_month", _NOW)
    assert start == _utc(2026, 7, 31, 22)  # 1 Aug 00:00 Prague
    assert end == _utc(2026, 8, 31, 22)  # 1 Sep 00:00 Prague


def test_date_window_future_and_unknown():
    assert date_window("future", _NOW) == (_NOW, None)
    assert date_window("last_year", _NOW) is None
    assert date_window("", _NOW) is None


def test_date_window_falls_back_to_utc_for_bad_zone(monkeypatch):
    monkeypatch.setattr(lookups, "instance_timezone", lambda: "Mars/Olympus")
    start, end = date_window("today", _NOW)
    assert (start, end) == (_utc(2026, 8, 1), _utc(2026, 8, 2))


def test_mongo_and_elastic_date_filters_share_the_window(monkeypatch):
    monkeypatch.setattr(lookups, "date_window", lambda f, now=None: (_utc(2026, 8, 1), _utc(2026, 8, 2)))
    assert mongo_date_filter("today") == {"$gte": _utc(2026, 8, 1), "$lt": _utc(2026, 8, 2)}
    assert elastic_date_filter("today") == {"gte": "2026-08-01T00:00:00+00:00", "lt": "2026-08-02T00:00:00+00:00"}
    monkeypatch.setattr(lookups, "date_window", lambda f, now=None: (_utc(2026, 8, 1), None))
    assert mongo_date_filter("future") == {"$gte": _utc(2026, 8, 1)}
    assert elastic_date_filter("future") == {"gte": "2026-08-01T00:00:00+00:00"}
    monkeypatch.setattr(lookups, "date_window", lambda f, now=None: None)
    assert mongo_date_filter("x") is None and elastic_date_filter("x") is None


def test_every_search_tool_uses_the_shared_date_filter_vocabulary():
    from sava.tools import get_tool

    for name in ("find_articles", "search_planning", "search_events"):
        prop = get_tool(name).parameters["properties"]["date_filter"]
        assert set(prop["enum"]) <= set(DATE_FILTERS), name
        assert prop["description"] == DATE_FILTER_DESCRIPTION, name
