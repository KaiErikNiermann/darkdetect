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
import weakref
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager

_running: weakref.WeakSet[subprocess.Popen[str]] = weakref.WeakSet()


def _stop_all() -> None:
    for p in tuple(_running):
        p.terminate()


atexit.register(_stop_all)


@contextmanager
def child_output(args: Sequence[str]) -> Generator[Iterator[str]]:
    """Run ``args`` and give the lines it prints, stopping it when the block ends.

    The child's stdin is a pipe that is never written to, so it reaches end of file when this
    process exits, however that happens; a child can watch it to exit along with us.
    """
    with subprocess.Popen(  # noqa: S603  # argv comes from the backends, never from the caller
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    ) as p:
        _running.add(p)
        try:
            yield iter(p.stdout or ())
        finally:
            _running.discard(p)
            # A no-op if it has already exited; otherwise Popen.__exit__ would wait on it forever
            p.terminate()
