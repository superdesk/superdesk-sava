"""Pure helpers in lookups: ISO-datetime validation and profile-schema splitting."""

import pytest

from sava.tools.lookups import split_required_optional, valid_iso_datetime


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
