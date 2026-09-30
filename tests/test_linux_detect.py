"""Tests for the Linux backend: gsettings parsing, and the portal on a private session bus."""

import queue
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Literal

import pytest

if sys.platform != "linux":
    pytest.skip("the Linux backend needs jeepney, installed on Linux only", allow_module_level=True)

from jeepney import (
    DBusAddress,
    HeaderFields,
    MessageType,
    message_bus,
    new_method_return,
    new_signal,
)
from jeepney.io.blocking import open_dbus_connection

from darkdetect import _linux_detect  # pyright: ignore[reportPrivateUsage]

Runner = Callable[..., subprocess.CompletedProcess[str]]

_PORTAL_NAME = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_SETTINGS_INTERFACE = "org.freedesktop.portal.Settings"
_TIMEOUT = 5.0

_BUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:path={socket}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def _fake_run(*outputs: str) -> Runner:
    """Return a stand-in for ``subprocess.run`` that yields ``outputs`` in order."""
    remaining: Iterator[str] = iter(outputs)

    def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=next(remaining), stderr="")

    return run


def _no_gsettings(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
    raise FileNotFoundError


@pytest.fixture(autouse=True)
def no_portal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the backend at a session bus that does not exist, so no portal answers."""
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", f"unix:path={tmp_path / 'no-bus'}")


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        (("'prefer-dark'\n",), "Dark"),
        (("'prefer-light'\n",), "Light"),
        (("'default'\n", "'Adwaita'\n"), "Light"),
        (("'default'\n", "'Adwaita-dark'\n"), "Dark"),
        (("'default'\n", ""), "Light"),
    ],
)
def test_theme_parses_gsettings_output(
    monkeypatch: pytest.MonkeyPatch,
    stdout: tuple[str, ...],
    expected: Literal["Dark", "Light"],
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run(*stdout))
    assert _linux_detect.theme() == expected


def test_theme_falls_back_to_gtk_theme_on_empty_color_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run("", "'Yaru-dark'\n"))
    assert _linux_detect.theme() == "Dark"


def test_theme_is_none_when_gsettings_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _no_gsettings)
    assert _linux_detect.theme() is None


def test_theme_is_none_when_gsettings_prints_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_run("", ""))
    assert _linux_detect.theme() is None


def test_session_bus_falls_back_to_the_user_bus_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/4242")
    assert _linux_detect._session_bus() == "unix:path=/run/user/4242/bus"  # pyright: ignore[reportPrivateUsage]


class FakePortal:
    """Serve the portal's Settings.Read on a private bus and emit SettingChanged on demand."""

    def __init__(self, address: str, color_scheme: int) -> None:
        self.color_scheme = color_scheme
        self._signals: queue.SimpleQueue[tuple[str, str, int]] = queue.SimpleQueue()
        self._stop = threading.Event()
        self._reads = threading.Semaphore(0)
        self._conn = open_dbus_connection(address)
        self._conn.send_and_get_reply(message_bus.RequestName(_PORTAL_NAME), timeout=_TIMEOUT)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def change(self, namespace: str, key: str, value: int) -> None:
        """Change a setting and announce it, as the portal does."""
        if (namespace, key) == ("org.freedesktop.appearance", "color-scheme"):
            self.color_scheme = value
        self._signals.put((namespace, key, value))

    def wait_for_reads(self, count: int) -> None:
        """Wait until ``count`` more Read calls have been answered."""
        for _ in range(count):
            assert self._reads.acquire(timeout=_TIMEOUT)

    def close(self) -> None:
        """Stop serving and leave the bus."""
        self._stop.set()
        self._thread.join(_TIMEOUT)
        self._conn.close()

    def _serve(self) -> None:
        # One thread owns the connection, so signals are sent from here too
        emitter = DBusAddress(_PORTAL_PATH, interface=_SETTINGS_INTERFACE)
        while not self._stop.is_set():
            while not self._signals.empty():
                namespace, key, value = self._signals.get()
                body = (namespace, key, ("u", value))
                self._conn.send(new_signal(emitter, "SettingChanged", "ssv", body))
            try:
                msg = self._conn.receive(timeout=0.05)
            except TimeoutError:
                continue
            if (
                msg.header.message_type == MessageType.method_call
                and msg.header.fields.get(HeaderFields.member) == "Read"
            ):
                # Read returns the setting as a variant nested in a variant
                body = (("v", ("u", self.color_scheme)),)
                self._conn.send(new_method_return(msg, "v", body))
                self._reads.release()


@pytest.fixture
def private_bus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    """Run a dbus-daemon of our own and make it the session bus."""
    if (daemon := shutil.which("dbus-daemon")) is None:
        pytest.skip("dbus-daemon is not installed")
    config = tmp_path / "bus.conf"
    config.write_text(_BUS_CONFIG.format(socket=tmp_path / "bus"))
    with subprocess.Popen(
        [daemon, f"--config-file={config}", "--nofork", "--print-address"],
        stdout=subprocess.PIPE,
        text=True,
    ) as proc:
        assert proc.stdout is not None
        address = proc.stdout.readline().strip()
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", address)
        try:
            yield address
        finally:
            proc.terminate()


@pytest.fixture
def portal(private_bus: str) -> Iterator[FakePortal]:
    fake = FakePortal(private_bus, color_scheme=1)
    try:
        yield fake
    finally:
        fake.close()


@pytest.mark.parametrize(("color_scheme", "expected"), [(1, "Dark"), (2, "Light")])
def test_theme_reads_the_portal(
    monkeypatch: pytest.MonkeyPatch,
    portal: FakePortal,
    color_scheme: int,
    expected: Literal["Dark", "Light"],
) -> None:
    monkeypatch.setattr(subprocess, "run", _no_gsettings)
    portal.color_scheme = color_scheme
    assert _linux_detect.theme() == expected


def test_theme_asks_gsettings_when_the_portal_has_no_preference(
    monkeypatch: pytest.MonkeyPatch, portal: FakePortal
) -> None:
    portal.color_scheme = 0
    monkeypatch.setattr(subprocess, "run", _fake_run("'default'\n", "'Adwaita-dark'\n"))
    assert _linux_detect.theme() == "Dark"
    monkeypatch.setattr(subprocess, "run", _no_gsettings)
    assert _linux_detect.theme() == "Light"


def test_theme_asks_gsettings_when_the_bus_has_no_portal(
    monkeypatch: pytest.MonkeyPatch, private_bus: str
) -> None:
    del private_bus
    monkeypatch.setattr(subprocess, "run", _fake_run("'prefer-dark'\n"))
    assert _linux_detect.theme() == "Dark"


def test_listener_reports_portal_changes(
    monkeypatch: pytest.MonkeyPatch, portal: FakePortal
) -> None:
    monkeypatch.setattr(subprocess, "run", _no_gsettings)
    seen: queue.SimpleQueue[str] = queue.SimpleQueue()

    def listen() -> None:
        # The listener runs until the bus goes away at teardown
        try:
            _linux_detect.listener(seen.put)
        except OSError:
            return

    threading.Thread(target=listen, daemon=True).start()
    # One Read checks the portal is there, the next, after subscribing, is the starting theme
    portal.wait_for_reads(2)
    # Nothing is reported for unrelated settings, or for a change that keeps the theme
    portal.change("org.gnome.desktop.interface", "font-name", 0)
    portal.change("org.freedesktop.appearance", "color-scheme", 1)
    portal.change("org.freedesktop.appearance", "color-scheme", 2)
    assert seen.get(timeout=_TIMEOUT) == "Light"
    portal.change("org.freedesktop.appearance", "color-scheme", 1)
    assert seen.get(timeout=_TIMEOUT) == "Dark"
    assert seen.empty()
