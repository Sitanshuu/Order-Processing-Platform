import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetProductRequest(_message.Message):
    __slots__ = ("product_id",)
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    def __init__(self, product_id: _Optional[str] = ...) -> None: ...

class ProductResponse(_message.Message):
    __slots__ = ("product_id", "name", "sku", "price", "currency", "is_active")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SKU_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    name: str
    sku: str
    price: float
    currency: str
    is_active: bool
    def __init__(self, product_id: _Optional[str] = ..., name: _Optional[str] = ..., sku: _Optional[str] = ..., price: _Optional[float] = ..., currency: _Optional[str] = ..., is_active: _Optional[bool] = ...) -> None: ...

class ValidateItem(_message.Message):
    __slots__ = ("product_id", "quantity")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    quantity: int
    def __init__(self, product_id: _Optional[str] = ..., quantity: _Optional[int] = ...) -> None: ...

class ValidateProductsRequest(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[ValidateItem]
    def __init__(self, items: _Optional[_Iterable[_Union[ValidateItem, _Mapping]]] = ...) -> None: ...

class ValidatedProductDetail(_message.Message):
    __slots__ = ("product_id", "name", "price", "is_valid", "error_message")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    IS_VALID_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    product_id: str
    name: str
    price: float
    is_valid: bool
    error_message: str
    def __init__(self, product_id: _Optional[str] = ..., name: _Optional[str] = ..., price: _Optional[float] = ..., is_valid: _Optional[bool] = ..., error_message: _Optional[str] = ...) -> None: ...

class ValidateProductsResponse(_message.Message):
    __slots__ = ("all_valid", "items", "total_amount")
    ALL_VALID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    all_valid: bool
    items: _containers.RepeatedCompositeFieldContainer[ValidatedProductDetail]
    total_amount: float
    def __init__(self, all_valid: _Optional[bool] = ..., items: _Optional[_Iterable[_Union[ValidatedProductDetail, _Mapping]]] = ..., total_amount: _Optional[float] = ...) -> None: ...
