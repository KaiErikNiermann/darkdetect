# -----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile, Eric Larson
#
#  Distributed under the terms of the 3-clause BSD License.
# -----------------------------------------------------------------------------

"""Linux backend using the XDG desktop portal, with gsettings as the fallback.

The portal's ``org.freedesktop.appearance`` ``color-scheme`` setting is what GNOME, KDE and
other desktops expose to sandboxed apps, and it is read over the session bus, so it works
where gsettings is missing (Vanilla OS) or answers for the wrong settings backend (a conda
environment, whose gsettings has no dconf module and reports the schema defaults).
"""

import os
import subprocess
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from enum import IntEnum
from typing import Literal

from jeepney import (
    AuthenticationError,
    DBusAddress,
    DBusErrorResponse,
    MatchRule,
    Message,
    message_bus,
    new_method_call,
)
from jeepney.io.blocking import DBusConnection, open_dbus_connection
from jeepney.wrappers import unwrap_msg

type Theme = Literal["Dark", "Light"]

_INTERFACE_SCHEMA = "org.gnome.desktop.interface"
_APPEARANCE_NAMESPACE = "org.freedesktop.appearance"
_PORTAL = DBusAddress(
    "/org/freedesktop/portal/desktop",
    bus_name="org.freedesktop.portal.Desktop",
    interface="org.freedesktop.portal.Settings",
)
# Seconds to wait on the portal, which the bus may first have to start
_DBUS_TIMEOUT = 2.0
# What connecting to the session bus or calling the portal raises when either is unavailable
_DBUS_ERRORS = (OSError, KeyError, RuntimeError, AuthenticationError, DBusErrorResponse)
# The settings theme() reads, as (namespace or schema, key)
_THEME_SETTINGS = frozenset(
    {
        (_APPEARANCE_NAMESPACE, "color-scheme"),
        (_INTERFACE_SCHEMA, "color-scheme"),
        (_INTERFACE_SCHEMA, "gtk-theme"),
    }
)


class _ColorScheme(IntEnum):
    """Values of the portal's ``org.freedesktop.appearance`` ``color-scheme`` setting."""

    NO_PREFERENCE = 0
    PREFER_DARK = 1
    PREFER_LIGHT = 2


def _session_bus() -> str:
    """Return the session bus address, falling back to the systemd user bus socket."""
    if address := os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return address
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return f"unix:path={runtime_dir}/bus"


def _read_color_scheme(conn: DBusConnection) -> int | None:
    """Ask the portal for its color-scheme; raises ``_DBUS_ERRORS`` if it cannot answer."""
    call = new_method_call(_PORTAL, "Read", "ss", (_APPEARANCE_NAMESPACE, "color-scheme"))
    match unwrap_msg(conn.send_and_get_reply(call, timeout=_DBUS_TIMEOUT)):
        # Read returns the value as a variant inside a variant; accept a single one as well
        case (("v", ("u", int() as scheme)),) | (("u", int() as scheme),):
            return scheme
        case _:
            return None


def _portal_color_scheme() -> int | None:
    """Return the portal's color-scheme, or None if there is no portal to ask."""
    try:
        with open_dbus_connection(_session_bus()) as conn:
            return _read_color_scheme(conn)
    except _DBUS_ERRORS:
        return None


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


def _gsettings_theme() -> Theme | None:
    """Return the theme gsettings reports, or None if it cannot be read."""
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


def theme() -> Theme | None:
    """Return the current theme, or None if it cannot be read."""
    match _portal_color_scheme():
        case _ColorScheme.PREFER_DARK:
            return "Dark"
        case _ColorScheme.PREFER_LIGHT:
            return "Light"
        case _ColorScheme.NO_PREFERENCE:
            return _gsettings_theme() or "Light"
        case _:
            return _gsettings_theme()


def _report_changes(callback: Callable[[str], None], changed: Iterable[tuple[str, str]]) -> None:
    """Call ``callback`` whenever a change to one of ``_THEME_SETTINGS`` changes the theme."""
    last = theme()
    for _ in filter(_THEME_SETTINGS.__contains__, changed):
        if (current := theme()) is not None and current != last:
            last = current
            callback(current)


def _portal_changes(conn: DBusConnection, queue: deque[Message]) -> Iterator[tuple[str, str]]:
    """Yield the (namespace, key) of every setting the portal reports as changed."""
    while True:
        match conn.recv_until_filtered(queue).body:
            case (str() as namespace, str() as key, *_):
                yield namespace, key
            case _:
                pass


def _subscribe_to_portal() -> tuple[DBusConnection, MatchRule] | None:
    """Subscribe to the portal's SettingChanged signal, or return None if there is no portal."""
    rule = MatchRule(
        type="signal",
        interface=_PORTAL.interface,
        member="SettingChanged",
        path=_PORTAL.object_path,
    )
    try:
        conn = open_dbus_connection(_session_bus())
    except _DBUS_ERRORS:
        return None
    try:
        # A bus without a portal still accepts the match rule, so check the portal answers
        _read_color_scheme(conn)
        unwrap_msg(conn.send_and_get_reply(message_bus.AddMatch(rule), timeout=_DBUS_TIMEOUT))
    except _DBUS_ERRORS:
        conn.close()
        return None
    return conn, rule


def _gsettings_listener(callback: Callable[[str], None]) -> None:
    """Report theme changes seen by ``gsettings monitor``."""
    try:
        p = subprocess.Popen(  # noqa: S603  # fixed argv
            ("gsettings", "monitor", _INTERFACE_SCHEMA),  # noqa: S607
            stdout=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as e:
        msg = "neither the XDG desktop portal nor gsettings is available"
        raise NotImplementedError(msg) from e
    with p:
        # Each line is "key: value"
        lines = p.stdout or ()
        _report_changes(callback, ((_INTERFACE_SCHEMA, line.partition(":")[0]) for line in lines))


def listener(callback: Callable[[str], None]) -> None:
    """Call ``callback`` with the new theme on every change."""
    if (subscription := _subscribe_to_portal()) is None:
        _gsettings_listener(callback)
        return
    conn, rule = subscription
    # Room for a burst of SettingChanged signals, of which only some are about the theme
    with conn, conn.filter(rule, bufsize=64) as queue:
        _report_changes(callback, _portal_changes(conn, queue))
