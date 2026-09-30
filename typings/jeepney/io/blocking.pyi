from collections import deque
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Self

from .. import Message
from ..bus_messages import MatchRule

class DBusConnection:
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...
    def close(self) -> None: ...
    def send(self, message: Message, serial: int | None = None) -> None: ...
    def receive(self, *, timeout: float | None = None) -> Message: ...
    def send_and_get_reply(self, message: Message, *, timeout: float | None = None) -> Message: ...
    def filter(
        self, rule: MatchRule, *, queue: deque[Message] | None = None, bufsize: int = 1
    ) -> AbstractContextManager[deque[Message]]: ...
    def recv_until_filtered(
        self, queue: deque[Message], *, timeout: float | None = None
    ) -> Message: ...

def open_dbus_connection(
    bus: str = "SESSION", enable_fds: bool = False, auth_timeout: float = 1.0
) -> DBusConnection: ...
