# -----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile
#
#  Distributed under the terms of the 3-clause BSD License.
# -----------------------------------------------------------------------------

"""Detect the OS dark mode setting."""

__version__ = "0.8.0"

import platform
import sys


def macos_supported_version() -> bool:
    """Return whether this macOS is at least 10.14 (first with dark mode)."""
    # platform is deleted at module end, so this is only callable during import
    sysver = platform.mac_ver()[0]  # noqa: F821  # typically 10.14.2 or 12.3
    major = int(sysver.split(".")[0])
    if major < 10:
        return False
    if major >= 11:
        return True
    minor = int(sysver.split(".")[1])
    return minor >= 14


if sys.platform == "darwin":
    if macos_supported_version():
        from ._mac_detect import *
    else:
        from ._dummy import *
elif sys.platform == "win32" and platform.release().isdigit() and int(platform.release()) >= 10:
    # Checks if running Windows 10 version 10.0.14393 (Anniversary Update) OR HIGHER. The
    # getwindowsversion method returns a tuple. The third item is the build number that we can
    # use to check if the user has a new enough version of Windows.
    winver = int(platform.version().split(".")[2])
    if winver >= 14393:
        from ._windows_detect import *
    else:
        from ._dummy import *
elif sys.platform == "linux":
    from ._linux_detect import *
else:
    from ._dummy import *

del sys, platform


def isDark() -> bool | None:
    """Return whether the theme is dark, or None if it is unknown."""
    return None if (current := theme()) is None else current == "Dark"


def isLight() -> bool | None:
    """Return whether the theme is light, or None if it is unknown."""
    return None if (current := theme()) is None else current == "Light"
