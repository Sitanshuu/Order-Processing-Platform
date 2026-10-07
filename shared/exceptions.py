from typing import Any, Dict, Optional


class AppBaseException(Exception):
    """Base domain exception with standardized error payload."""
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class EntityNotFoundException(AppBaseException):
    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(
            message=f"{entity_name} with id '{entity_id}' was not found.",
            code=f"{entity_name.upper()}_NOT_FOUND",
            status_code=404,
            details={"entity": entity_name, "id": entity_id},
        )


class InsufficientStockException(AppBaseException):
    def __init__(self, product_id: str, requested: int, available: int):
        super().__init__(
            message=f"Insufficient stock for product {product_id}. Requested: {requested}, Available: {available}.",
            code="INSUFFICIENT_STOCK",
            status_code=400,
            details={"product_id": product_id, "requested": requested, "available": available},
        )


class InvalidStateTransitionException(AppBaseException):
    def __init__(self, entity_name: str, current_state: str, attempted_state: str):
        super().__init__(
            message=f"Invalid state transition for {entity_name}: cannot transition from '{current_state}' to '{attempted_state}'.",
            code="INVALID_STATE_TRANSITION",
            status_code=400,
            details={"entity": entity_name, "current_state": current_state, "attempted_state": attempted_state},
        )


class IdempotencyConflictException(AppBaseException):
    def __init__(self, key: str, message: str = "A request with this Idempotency-Key is currently being processed or has completed."):
        super().__init__(
            message=message,
            code="IDEMPOTENCY_CONFLICT",
            status_code=409,
            details={"idempotency_key": key},
        )


class PaymentProcessingException(AppBaseException):
    def __init__(self, message: str, order_id: str, reason: str = "SIMULATED_FAILURE"):
        super().__init__(
            message=message,
            code="PAYMENT_FAILED",
            status_code=402,
            details={"order_id": order_id, "reason": reason},
        )


class AuthenticationException(AppBaseException):
    def __init__(self, message: str = "Unauthorized: Invalid or expired token"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401,
        )


class AuthorizationException(AppBaseException):
    def __init__(self, message: str = "Forbidden: Insufficient permissions"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )
