"""Unit tests for the gsettings parsing in the Linux backend."""

import subprocess
from collections.abc import Callable, Iterator
from typing import Literal

import pytest

from darkdetect import _linux_detect  # pyright: ignore[reportPrivateUsage]

Runner = Callable[..., subprocess.CompletedProcess[str]]


def _fake_run(*outputs: str) -> Runner:
    """Return a stand-in for ``subprocess.run`` that yields ``outputs`` in order."""
    remaining: Iterator[str] = iter(outputs)

    def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=next(remaining), stderr="")

    return run


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("'prefer-dark'\n", "Dark"),
        ("'Adwaita-dark'\n", "Dark"),
        ("'Adwaita'\n", "Light"),
        ("'default'\n", "Light"),
    ],
)
def test_theme_parses_gsettings_output(
    monkeypatch: pytest.MonkeyPatch, stdout: str, expected: Literal["Dark", "Light"]
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout))
    assert _linux_detect.theme() == expected


def test_theme_falls_back_to_gtk_theme_on_empty_color_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run("", "'Yaru-dark'\n"))
    assert _linux_detect.theme() == "Dark"


def test_theme_is_none_when_gsettings_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    assert _linux_detect.theme() is None


def test_theme_is_none_when_gsettings_prints_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run("", ""))
    assert _linux_detect.theme() is None


def test_is_dark_and_is_light_follow_theme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_linux_detect, "theme", lambda: "Dark")
    assert _linux_detect.isDark()
    assert not _linux_detect.isLight()
