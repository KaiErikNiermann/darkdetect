# Minimal stubs for the parts of jeepney darkdetect uses; jeepney ships no type information.
# Drop them once jeepney ships its own (https://gitlab.com/takluyver/jeepney/-/issues/11).

from enum import Enum
from typing import Any

from .bus_messages import MatchRule as MatchRule
from .bus_messages import message_bus as message_bus
from .wrappers import DBusAddress as DBusAddress
from .wrappers import DBusErrorResponse as DBusErrorResponse
from .wrappers import new_method_call as new_method_call
from .wrappers import new_method_return as new_method_return
from .wrappers import new_signal as new_signal

class MessageType(Enum):
    method_call = 1
    method_return = 2
    error = 3
    signal = 4

class HeaderFields(Enum):
    path = 1
    interface = 2
    member = 3
    error_name = 4
    reply_serial = 5
    destination = 6
    sender = 7
    signature = 8
    unix_fds = 9

class Header:
    message_type: MessageType
    fields: dict[HeaderFields, Any]

class Message:
    header: Header
    body: tuple[Any, ...]

class AuthenticationError(ValueError): ...
