import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetOrderRequest(_message.Message):
    __slots__ = ("order_id",)
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    def __init__(self, order_id: _Optional[str] = ...) -> None: ...

class GetOrderStatusRequest(_message.Message):
    __slots__ = ("order_id",)
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    def __init__(self, order_id: _Optional[str] = ...) -> None: ...

class OrderItemMessage(_message.Message):
    __slots__ = ("product_id", "product_name", "quantity", "unit_price", "subtotal")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_NAME_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    UNIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    SUBTOTAL_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float
    def __init__(self, product_id: _Optional[str] = ..., product_name: _Optional[str] = ..., quantity: _Optional[int] = ..., unit_price: _Optional[float] = ..., subtotal: _Optional[float] = ...) -> None: ...

class OrderResponse(_message.Message):
    __slots__ = ("order_id", "customer_id", "status", "total_amount", "currency", "items", "created_at", "updated_at", "correlation_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CUSTOMER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    customer_id: str
    status: str
    total_amount: float
    currency: str
    items: _containers.RepeatedCompositeFieldContainer[OrderItemMessage]
    created_at: str
    updated_at: str
    correlation_id: str
    def __init__(self, order_id: _Optional[str] = ..., customer_id: _Optional[str] = ..., status: _Optional[str] = ..., total_amount: _Optional[float] = ..., currency: _Optional[str] = ..., items: _Optional[_Iterable[_Union[OrderItemMessage, _Mapping]]] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class OrderStatusResponse(_message.Message):
    __slots__ = ("order_id", "status", "updated_at")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    status: str
    updated_at: str
    def __init__(self, order_id: _Optional[str] = ..., status: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...
