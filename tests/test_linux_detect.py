"""Unit tests for the gsettings parsing in the Linux backend."""

import subprocess
from collections.abc import Callable, Iterator
from typing import Literal

import pytest

from darkdetect import _linux_detect  # pyright: ignore[reportPrivateUsage]

Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _fake_run(*outputs: bytes) -> Runner:
    """Return a stand-in for ``subprocess.run`` that yields ``outputs`` in order."""
    remaining: Iterator[bytes] = iter(outputs)

    def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args, 0, stdout=next(remaining), stderr=b"")

    return run


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        (b"'prefer-dark'\n", "Dark"),
        (b"'Adwaita-dark'\n", "Dark"),
        (b"'Adwaita'\n", "Light"),
        (b"'default'\n", "Light"),
    ],
)
def test_theme_parses_gsettings_output(
    monkeypatch: pytest.MonkeyPatch, stdout: bytes, expected: Literal["Dark", "Light"]
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout))
    assert _linux_detect.theme() == expected


def test_theme_falls_back_to_gtk_theme_on_empty_color_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run(b"", b"'Yaru-dark'\n"))
    assert _linux_detect.theme() == "Dark"


def test_theme_is_light_when_gsettings_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    assert _linux_detect.theme() == "Light"


def test_is_dark_and_is_light_follow_theme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_linux_detect, "theme", lambda: "Dark")
    assert _linux_detect.isDark()
    assert not _linux_detect.isLight()
