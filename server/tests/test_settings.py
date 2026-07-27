"""Settings resolution: environment override, defaults, and integer guards."""

from sava.default_settings import get_int_setting, get_setting


def test_get_setting_env_takes_precedence(monkeypatch):
    monkeypatch.setenv("SAVA_MODEL", "vendor/custom-model")
    assert get_setting("SAVA_MODEL") == "vendor/custom-model"


def test_get_setting_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("SAVA_MODEL", raising=False)
    assert get_setting("SAVA_MODEL") == "openai/gpt-oss-120b"


def test_get_setting_unknown_key_is_empty(monkeypatch):
    monkeypatch.delenv("SAVA_TOTALLY_UNKNOWN", raising=False)
    assert get_setting("SAVA_TOTALLY_UNKNOWN") == ""


def test_get_int_setting_valid(monkeypatch):
    monkeypatch.setenv("SAVA_MAX_STEPS", "9")
    assert get_int_setting("SAVA_MAX_STEPS") == 9


def test_get_int_setting_bad_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SAVA_MAX_STEPS", "not-an-int")
    assert get_int_setting("SAVA_MAX_STEPS") == 6


def test_get_int_setting_clamps_to_minimum(monkeypatch):
    monkeypatch.setenv("SAVA_MAX_STEPS", "0")
    assert get_int_setting("SAVA_MAX_STEPS") == 1
