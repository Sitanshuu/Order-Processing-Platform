from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StatusResponse(_message.Message):
    __slots__ = ("success", "message", "code")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    code: str
    def __init__(self, success: _Optional[bool] = ..., message: _Optional[str] = ..., code: _Optional[str] = ...) -> None: ...

class Money(_message.Message):
    __slots__ = ("currency", "amount")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    currency: str
    amount: float
    def __init__(self, currency: _Optional[str] = ..., amount: _Optional[float] = ...) -> None: ...
