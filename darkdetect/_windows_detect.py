"""Windows backend using the registry."""

import ctypes
import ctypes.wintypes
import sys
from collections.abc import Callable
from typing import Literal

if sys.platform != "win32":
    # Also makes pyright treat the rest of the module as unreachable off Windows, where winreg
    # and ctypes.windll do not exist; scripts/pyright-windows.json checks it as Windows.
    msg = "the Windows backend only works on Windows"
    raise ImportError(msg)

from winreg import HKEY_CURRENT_USER as hkey  # noqa: N811
from winreg import OpenKey as getKey
from winreg import QueryValueEx as getSubkeyValue

advapi32 = ctypes.windll.advapi32

# LSTATUS RegOpenKeyExA(
#     HKEY hKey,
#     LPCSTR lpSubKey,
#     DWORD ulOptions,
#     REGSAM samDesired,
#     PHKEY phkResult
# );
advapi32.RegOpenKeyExA.argtypes = (
    ctypes.wintypes.HKEY,
    ctypes.wintypes.LPCSTR,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.wintypes.HKEY),
)
advapi32.RegOpenKeyExA.restype = ctypes.wintypes.LONG

# LSTATUS RegQueryValueExA(
#     HKEY hKey,
#     LPCSTR lpValueName,
#     LPDWORD lpReserved,
#     LPDWORD lpType,
#     LPBYTE lpData,
#     LPDWORD lpcbData
# );
advapi32.RegQueryValueExA.argtypes = (
    ctypes.wintypes.HKEY,
    ctypes.wintypes.LPCSTR,
    ctypes.wintypes.LPDWORD,
    ctypes.wintypes.LPDWORD,
    ctypes.wintypes.LPBYTE,
    ctypes.wintypes.LPDWORD,
)
advapi32.RegQueryValueExA.restype = ctypes.wintypes.LONG

# LSTATUS RegNotifyChangeKeyValue(
#     HKEY hKey,
#     WINBOOL bWatchSubtree,
#     DWORD dwNotifyFilter,
#     HANDLE hEvent,
#     WINBOOL fAsynchronous
# );
advapi32.RegNotifyChangeKeyValue.argtypes = (
    ctypes.wintypes.HKEY,
    ctypes.wintypes.BOOL,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.BOOL,
)
advapi32.RegNotifyChangeKeyValue.restype = ctypes.wintypes.LONG


def theme() -> Literal["Dark", "Light"] | None:
    """Use the Windows Registry to detect if the user is using Dark Mode."""
    # Registry will return 0 if Windows is in Dark Mode and 1 if Windows is in Light Mode. This
    # dictionary converts that output into the text that the program is expecting.
    valueMeaning: dict[int, Literal["Dark", "Light"]] = {0: "Dark", 1: "Light"}
    # In HKEY_CURRENT_USER, get the Personalisation Key.
    try:
        key = getKey(hkey, "Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize")
        # In the Personalisation Key, get the AppsUseLightTheme subkey. This returns a tuple.
        # The first item in the tuple is the result we want (0 or 1 indicating Dark Mode or
        # Light Mode); the other value is the type of subkey e.g. DWORD, QWORD, String, etc.
        subkey = getSubkeyValue(key, "AppsUseLightTheme")[0]
    except FileNotFoundError:
        # some headless Windows instances (e.g. GitHub Actions or Docker images) do not have this
        # key
        return None
    return valueMeaning[subkey]


def isDark() -> bool | None:
    """Return whether the theme is dark, or None if unknown."""
    if theme() is not None:
        return theme() == "Dark"
    return None


def isLight() -> bool | None:
    """Return whether the theme is light, or None if unknown."""
    if theme() is not None:
        return theme() == "Light"
    return None


def listener(callback: Callable[[str], None]) -> None:
    """Call ``callback`` with the new theme on every change."""
    hKey = ctypes.wintypes.HKEY()
    advapi32.RegOpenKeyExA(
        ctypes.wintypes.HKEY(0x80000001),  # HKEY_CURRENT_USER
        ctypes.wintypes.LPCSTR(
            b"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
        ),
        ctypes.wintypes.DWORD(),
        ctypes.wintypes.DWORD(0x00020019),  # KEY_READ
        ctypes.byref(hKey),
    )

    dwSize = ctypes.wintypes.DWORD(ctypes.sizeof(ctypes.wintypes.DWORD))
    queryValueLast = ctypes.wintypes.DWORD()
    queryValue = ctypes.wintypes.DWORD()
    advapi32.RegQueryValueExA(
        hKey,
        ctypes.wintypes.LPCSTR(b"AppsUseLightTheme"),
        ctypes.wintypes.LPDWORD(),
        ctypes.wintypes.LPDWORD(),
        ctypes.cast(ctypes.byref(queryValueLast), ctypes.wintypes.LPBYTE),
        ctypes.byref(dwSize),
    )

    while True:
        advapi32.RegNotifyChangeKeyValue(
            hKey,
            ctypes.wintypes.BOOL(True),
            ctypes.wintypes.DWORD(0x00000004),  # REG_NOTIFY_CHANGE_LAST_SET
            ctypes.wintypes.HANDLE(None),
            ctypes.wintypes.BOOL(False),
        )
        advapi32.RegQueryValueExA(
            hKey,
            ctypes.wintypes.LPCSTR(b"AppsUseLightTheme"),
            ctypes.wintypes.LPDWORD(),
            ctypes.wintypes.LPDWORD(),
            ctypes.cast(ctypes.byref(queryValue), ctypes.wintypes.LPBYTE),
            ctypes.byref(dwSize),
        )
        if queryValueLast.value != queryValue.value:
            queryValueLast.value = queryValue.value
            callback("Light" if queryValue.value else "Dark")
