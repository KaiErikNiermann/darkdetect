from typing import Any

from . import Message

class DBusAddress:
    object_path: str
    bus_name: str | None
    interface: str | None
    def __init__(
        self, object_path: str, bus_name: str | None = None, interface: str | None = None
    ) -> None: ...

class DBusErrorResponse(Exception):
    name: str | None
    data: tuple[Any, ...]
    def __init__(self, msg: Message) -> None: ...

def new_method_call(
    remote_obj: DBusAddress, method: str, signature: str | None = None, body: tuple[Any, ...] = ()
) -> Message: ...
def new_method_return(
    parent_msg: Message, signature: str | None = None, body: tuple[Any, ...] = ()
) -> Message: ...
def new_signal(
    emitter: DBusAddress, signal: str, signature: str | None = None, body: tuple[Any, ...] = ()
) -> Message: ...
def unwrap_msg(msg: Message) -> tuple[Any, ...]: ...
