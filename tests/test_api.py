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


@pytest.mark.parametrize(
    ("version", "supported"),
    [
        ("10.0.14393", True),  # Windows 10 1607 and Server 2016
        ("10.0.20348", True),  # Windows Server 2022, whose release() is "2022Server"
        ("10.0.26100", True),  # Windows 11 24H2
        ("10.0.10586", False),  # Windows 10 1511
        ("6.3.9600", False),  # Windows 8.1
        ("", False),
    ],
)
def test_windows_supported(version: str, supported: bool) -> None:
    assert darkdetect._windows_supported(version) is supported  # pyright: ignore[reportPrivateUsage]
