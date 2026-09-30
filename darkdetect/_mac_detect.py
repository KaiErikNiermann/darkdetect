# -----------------------------------------------------------------------------
#  Copyright (C) 2019 Alberto Sottile
#
#  Distributed under the terms of the 3-clause BSD License.
# -----------------------------------------------------------------------------

"""macOS backend using the Objective-C runtime."""

# PyObjC ships no type information, so everything imported from it is Unknown to pyright.
# pyright: reportMissingImports=false, reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false, reportUntypedBaseClass=false
# pyright: reportPossiblyUnboundVariable=false, reportMissingParameterType=false
# pyright: reportUnknownParameterType=false

import ctypes
import ctypes.util
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

try:
    from Foundation import (
        NSKeyValueChangeNewKey,
        NSKeyValueObservingOptionNew,
        NSObject,
        NSUserDefaults,
    )
    from PyObjCTools import AppHelper

    _can_listen = True
except ModuleNotFoundError:
    _can_listen = False


try:
    # macOS Big Sur+ use "a built-in dynamic linker cache of all system-provided libraries"
    appkit = ctypes.cdll.LoadLibrary("AppKit.framework/AppKit")
    objc = ctypes.cdll.LoadLibrary("libobjc.dylib")
except OSError:
    # revert to full path for older OS versions and hardened programs
    appkit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))  # pyright: ignore[reportArgumentType]
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))  # pyright: ignore[reportArgumentType]

void_p = ctypes.c_void_p
ull = ctypes.c_uint64

objc.objc_getClass.restype = void_p
objc.sel_registerName.restype = void_p

# See https://docs.python.org/3/library/ctypes.html#function-prototypes for arguments description
MSGPROTOTYPE = ctypes.CFUNCTYPE(void_p, void_p, void_p, void_p)
msg = MSGPROTOTYPE(("objc_msgSend", objc), ((1, "", None), (1, "", None), (1, "", None)))


def _utf8(s: str | bytes) -> bytes:
    if not isinstance(s, bytes):
        s = s.encode("utf8")
    return s


def n(name: str) -> int | None:
    return objc.sel_registerName(_utf8(name))


def C(classname: str) -> int | None:
    return objc.objc_getClass(_utf8(classname))


def theme() -> str:
    """Return the current theme."""
    NSAutoreleasePool = objc.objc_getClass("NSAutoreleasePool")
    pool = msg(NSAutoreleasePool, n("alloc"))
    pool = msg(pool, n("init"))

    NSUserDefaults = C("NSUserDefaults")
    stdUserDef = msg(NSUserDefaults, n("standardUserDefaults"))

    NSString = C("NSString")

    key = msg(NSString, n("stringWithUTF8String:"), _utf8("AppleInterfaceStyle"))
    appearanceNS = msg(stdUserDef, n("stringForKey:"), void_p(key))
    appearanceC = msg(appearanceNS, n("UTF8String"))

    out = ctypes.string_at(appearanceC) if appearanceC is not None else None

    msg(pool, n("release"))

    if out is not None:
        return out.decode("utf-8")
    return "Light"


def isDark() -> bool:
    """Return whether the theme is dark."""
    return theme() == "Dark"


def isLight() -> bool:
    """Return whether the theme is light."""
    return theme() == "Light"


def _listen_child() -> None:  # pyright: ignore[reportUnusedFunction]
    """Run by a child process, install an observer and print theme on change."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    OBSERVED_KEY = "AppleInterfaceStyle"

    class Observer(NSObject):
        def observeValueForKeyPath_ofObject_change_context_(
            self,
            _path: object,
            _object: object,
            changeDescription: dict[object, object],
            _context: object,
        ) -> None:
            result = changeDescription[NSKeyValueChangeNewKey]
            try:
                print(f"{'Light' if result is None else result}", flush=True)  # noqa: T201
            except OSError:
                os._exit(1)

    observer = Observer.new()  # Keep a reference alive after installing
    defaults = NSUserDefaults.standardUserDefaults()
    defaults.addObserver_forKeyPath_options_context_(
        observer, OBSERVED_KEY, NSKeyValueObservingOptionNew, 0
    )

    AppHelper.runConsoleEventLoop()


def listener(callback: Callable[[str], None]) -> None:
    """Call ``callback`` with the new theme on every change."""
    if not _can_listen:
        raise NotImplementedError()
    with subprocess.Popen(
        (sys.executable, "-c", "import _mac_detect as m; m._listen_child()"),
        stdout=subprocess.PIPE,
        universal_newlines=True,
        cwd=Path(__file__).parent,
    ) as p:
        for line in p.stdout or ():
            callback(line.strip())
