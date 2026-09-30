"""Tests for the platform-independent helpers in the package entry point."""

import pytest

import darkdetect


@pytest.mark.parametrize(
    ("current", "dark", "light"),
    [("Dark", True, False), ("Light", False, True), (None, None, None)],
)
def test_is_dark_and_is_light_follow_theme(
    monkeypatch: pytest.MonkeyPatch, current: str | None, dark: bool | None, light: bool | None
) -> None:
    monkeypatch.setattr(darkdetect, "theme", lambda: current)
    assert darkdetect.isDark() is dark
    assert darkdetect.isLight() is light
