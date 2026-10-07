import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StockItem(_message.Message):
    __slots__ = ("product_id", "quantity")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    quantity: int
    def __init__(self, product_id: _Optional[str] = ..., quantity: _Optional[int] = ...) -> None: ...

class GetStockRequest(_message.Message):
    __slots__ = ("product_id",)
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    def __init__(self, product_id: _Optional[str] = ...) -> None: ...

class GetStockResponse(_message.Message):
    __slots__ = ("product_id", "available_quantity", "reserved_quantity", "total_quantity")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    RESERVED_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    TOTAL_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    available_quantity: int
    reserved_quantity: int
    total_quantity: int
    def __init__(self, product_id: _Optional[str] = ..., available_quantity: _Optional[int] = ..., reserved_quantity: _Optional[int] = ..., total_quantity: _Optional[int] = ...) -> None: ...

class ReserveStockRequest(_message.Message):
    __slots__ = ("order_id", "items", "correlation_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    items: _containers.RepeatedCompositeFieldContainer[StockItem]
    correlation_id: str
    def __init__(self, order_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[StockItem, _Mapping]]] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class ReserveStockResponse(_message.Message):
    __slots__ = ("success", "reservation_id", "message", "error_code")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    RESERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    reservation_id: str
    message: str
    error_code: str
    def __init__(self, success: _Optional[bool] = ..., reservation_id: _Optional[str] = ..., message: _Optional[str] = ..., error_code: _Optional[str] = ...) -> None: ...

class ReleaseStockRequest(_message.Message):
    __slots__ = ("order_id", "reservation_id", "correlation_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    RESERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    reservation_id: str
    correlation_id: str
    def __init__(self, order_id: _Optional[str] = ..., reservation_id: _Optional[str] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class ReleaseStockResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: _Optional[bool] = ..., message: _Optional[str] = ...) -> None: ...

class ConfirmStockRequest(_message.Message):
    __slots__ = ("order_id", "reservation_id", "correlation_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    RESERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    reservation_id: str
    correlation_id: str
    def __init__(self, order_id: _Optional[str] = ..., reservation_id: _Optional[str] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class ConfirmStockResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: _Optional[bool] = ..., message: _Optional[str] = ...) -> None: ...
