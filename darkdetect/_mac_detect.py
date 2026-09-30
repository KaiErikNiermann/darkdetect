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
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from ._process import child_output

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


def _load(name: str) -> ctypes.CDLL:
    """Load a system library by name; PyInstaller warns about LoadLibrary given a path."""
    # find_library also finds libraries that live only in the dyld cache (Big Sur and later)
    if (path := ctypes.util.find_library(name)) is None:
        # LoadLibrary(None) would quietly return the main program instead
        msg = f"cannot find the {name} library"
        raise OSError(msg)
    return ctypes.cdll.LoadLibrary(path)


# Loaded for its side effect of registering the Cocoa classes theme() looks up
appkit = _load("AppKit")
objc = _load("objc")

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


def _exit_with_parent() -> None:
    """Exit once stdin, a pipe from the parent, reaches end of file as the parent exits."""
    sys.stdin.read()
    os._exit(0)


def _listen_child() -> None:  # pyright: ignore[reportUnusedFunction]
    """Run by a child process, install an observer and print theme on change."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # Even a parent that is killed outright closes the pipe, so this child never outlives it
    threading.Thread(target=_exit_with_parent, daemon=True).start()

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


_CHILD_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from darkdetect._mac_detect import _listen_child; _listen_child()"
)


def listener(callback: Callable[[str], None]) -> None:
    """Call ``callback`` with the new theme on every change."""
    if not _can_listen:
        raise NotImplementedError()
    if getattr(sys, "frozen", False) and not Path(sys.executable).name.startswith("python"):
        # sys.executable is the app itself, which would ignore -c and start another copy
        msg = "the macOS listener needs a Python interpreter; frozen apps are not supported"
        raise NotImplementedError(msg)
    # The package's parent goes on the child's path explicitly: the working directory is not
    # on it under PYTHONSAFEPATH, and the caller may have imported darkdetect from anywhere
    with child_output(
        (sys.executable, "-c", _CHILD_SCRIPT, str(Path(__file__).parents[1]))
    ) as lines:
        for line in lines:
            callback(line.strip())
