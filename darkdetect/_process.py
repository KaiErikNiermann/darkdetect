# -----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile
#
#  Distributed under the terms of the 3-clause BSD License.
# -----------------------------------------------------------------------------

"""Child processes that listeners read theme changes from.

Listeners usually run in a daemon thread, which the interpreter abandons at exit without
unwinding it, so a child it started would outlive the program. Every child started here is
stopped when its listener returns or raises, and at interpreter exit.
"""

import atexit
import subprocess
import tempfile
import weakref
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager

_running: weakref.WeakSet[subprocess.Popen[str]] = weakref.WeakSet()
# Children stopped at exit, whose listener then ends without that being an error
_stopped: weakref.WeakSet[subprocess.Popen[str]] = weakref.WeakSet()


def _stop_all() -> None:
    for p in tuple(_running):
        _stopped.add(p)
        p.terminate()


atexit.register(_stop_all)


@contextmanager
def child_output(args: Sequence[str]) -> Generator[Iterator[str]]:
    """Run ``args`` and give the lines it prints, stopping it when the block ends.

    Raises ChildProcessError if the child fails, rather than letting the listener end quietly.

    The child's stdin is a pipe that is never written to, so it reaches end of file when this
    process exits, however that happens; a child can watch it to exit along with us.
    """
    # stderr goes to a file, as a pipe nobody reads until the end could fill and block the child
    with (
        tempfile.TemporaryFile("w+") as stderr,
        subprocess.Popen(  # noqa: S603  # argv comes from the backends, never from the caller
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
        ) as p,
    ):
        _running.add(p)
        try:
            yield iter(p.stdout or ())
            # Output ended, so the child exited; a listener's child only does that when it fails
            # (a signal counts too, as a negative status, unless it was ours at exit)
            if p.wait() != 0 and p not in _stopped:
                stderr.seek(0)
                msg = f"{args[0]} exited with status {p.returncode}: {stderr.read().strip()}"
                raise ChildProcessError(msg)
        finally:
            _running.discard(p)
            # A no-op if it has already exited; otherwise Popen.__exit__ would wait on it forever
            p.terminate()
