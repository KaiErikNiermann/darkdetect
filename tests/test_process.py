"""Tests that listener child processes do not outlive their listener or the program."""

import os
import subprocess
import sys
import textwrap
import time

import pytest

from darkdetect import _process  # pyright: ignore[reportPrivateUsage]

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the children are POSIX tools")

# Prints its pid, then sleeps until stopped, like gsettings monitor waiting for a change
_CHILD = (sys.executable, "-c", "import os, time; print(os.getpid(), flush=True); time.sleep(60)")


def _gone(pid: int, timeout: float = 5.0) -> bool:
    """Return whether ``pid`` exits within ``timeout`` seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def test_child_is_stopped_when_the_listener_raises() -> None:
    pid = 0
    with pytest.raises(RuntimeError), _process.child_output(_CHILD) as lines:
        pid = int(next(lines))
        raise RuntimeError
    assert _gone(pid)


def test_child_is_stopped_when_the_program_exits() -> None:
    # A listener in a daemon thread, as the README suggests, is never unwound at exit
    script = textwrap.dedent(
        f"""
        import threading
        from darkdetect import _process

        def listen():
            with _process.child_output({_CHILD!r}) as lines:
                for line in lines:
                    print(line, end="", flush=True)

        threading.Thread(target=listen, daemon=True).start()
        threading.Event().wait(1)
        """
    )
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True, timeout=30
    )
    assert _gone(int(out.stdout))
