"""Pure helpers in lookups: ISO-datetime validation and profile-schema splitting."""

import re

import pytest

from sava.tools.lookups import (
    MAX_RESULTS,
    contains,
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
