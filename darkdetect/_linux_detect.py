# -----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile, Eric Larson
#
#  Distributed under the terms of the 3-clause BSD License.
# -----------------------------------------------------------------------------

"""Linux backend using gsettings."""

import subprocess
from collections.abc import Callable
from typing import Literal


def theme() -> Literal["Dark", "Light"]:
    """Return the current theme."""
    try:
        # Using the freedesktop specifications for checking dark mode
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],  # noqa: S607
            capture_output=True,
            check=False,
        )
        stdout = out.stdout.decode()
        # If not found then trying older gtk-theme method
        if len(stdout) < 1:
            out = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],  # noqa: S607
                capture_output=True,
                check=False,
            )
            stdout = out.stdout.decode()
    except Exception:
        return "Light"
    # we have a string, now remove start and end quote
    theme = stdout.lower().strip()[1:-1]
    if "-dark" in theme.lower():
        return "Dark"
    return "Light"


def isDark() -> bool:
    """Return whether the theme is dark."""
    return theme() == "Dark"


def isLight() -> bool:
    """Return whether the theme is light."""
    return theme() == "Light"


def listener(callback: Callable[[str], None]) -> None:
    """Call ``callback`` with the new theme on every change."""
    with subprocess.Popen(
        ("gsettings", "monitor", "org.gnome.desktop.interface", "gtk-theme"),  # noqa: S607
        stdout=subprocess.PIPE,
        universal_newlines=True,
    ) as p:
        for line in p.stdout or ():
            callback(
                "Dark"
                if "-dark" in line.strip().removeprefix("gtk-theme: '").removesuffix("'").lower()
                else "Light"
            )
