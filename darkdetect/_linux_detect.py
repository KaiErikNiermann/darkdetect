# -----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile, Eric Larson
#
#  Distributed under the terms of the 3-clause BSD License.
# -----------------------------------------------------------------------------

"""Linux backend using gsettings."""

import subprocess
from collections.abc import Callable
from typing import Literal

_INTERFACE_SCHEMA = "org.gnome.desktop.interface"


def _gsettings(key: str) -> str | None:
    """Return a key of the GNOME interface schema, or None if gsettings cannot read it."""
    try:
        out = subprocess.run(  # noqa: S603  # fixed argv, key is one of ours
            ["gsettings", "get", _INTERFACE_SCHEMA, key],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    # gsettings prints GVariant text, so a string value comes wrapped in single quotes
    return out.stdout.strip().strip("'") or None


def theme() -> Literal["Dark", "Light"] | None:
    """Return the current theme, or None if it cannot be read."""
    match _gsettings("color-scheme"):
        case "prefer-dark":
            return "Dark"
        case "prefer-light":
            return "Light"
        case scheme:
            # "default" or a GNOME older than 42: a dark GTK theme still makes apps dark
            if (gtk_theme := _gsettings("gtk-theme")) is None:
                return None if scheme is None else "Light"
            return "Dark" if "-dark" in gtk_theme.lower() else "Light"


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
