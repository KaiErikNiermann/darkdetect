# -----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile
#
#  Distributed under the terms of the 3-clause BSD License.
# -----------------------------------------------------------------------------

"""Fallback backend for unsupported platforms."""

import typing


def theme() -> None:
    """Return no theme."""
    return


def listener(callback: typing.Callable[[str], None]) -> None:
    """Raise, as listening is unsupported here."""
    raise NotImplementedError()
