"""Tests for the macOS listener's child process, run on the macOS CI runner."""

import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

if sys.platform != "darwin":
    pytest.skip("the macOS listener runs on macOS only", allow_module_level=True)

import darkdetect
from darkdetect import _mac_detect  # pyright: ignore[reportPrivateUsage]


def test_listener_child_keeps_running() -> None:
    errors: queue.SimpleQueue[BaseException] = queue.SimpleQueue()

    def listen() -> None:
        try:
            darkdetect.listener(print)
        except Exception as e:  # reported to the test thread below
            errors.put(e)

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()
    # A child that cannot start its observer exits at once, and the listener raises
    thread.join(5)
    assert errors.empty(), errors.get()
    assert thread.is_alive()


def test_listener_child_exits_when_its_stdin_closes() -> None:
    package_parent = str(Path(_mac_detect.__file__).parents[1])
    with subprocess.Popen(
        [sys.executable, "-c", _mac_detect._CHILD_SCRIPT, package_parent],  # pyright: ignore[reportPrivateUsage]
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ) as child:
        with pytest.raises(subprocess.TimeoutExpired):
            child.wait(2)
        assert child.stdin is not None
        child.stdin.close()
        assert child.wait(5) == 0


def test_listener_refuses_a_frozen_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/Applications/Some.app/Contents/MacOS/Some")
    with pytest.raises(NotImplementedError, match="frozen"):
        darkdetect.listener(print)
