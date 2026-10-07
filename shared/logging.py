import logging
import json
import sys
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import contextvars

correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)
request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
service_name_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("service_name", default="unknown-service")


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter for enterprise observability.
    Formats logs with ISO UTC timestamps, log level, service name, correlation ID,
    request ID, event details, and error stack traces.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": service_name_ctx.get(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        corr_id = correlation_id_ctx.get()
        if corr_id:
            log_obj["correlation_id"] = corr_id

        req_id = request_id_ctx.get()
        if req_id:
            log_obj["request_id"] = req_id

        # Attach extra structured fields passed in log calls (e.g. logger.info("...", extra={"order_id": ...}))
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            for k, v in record.extra.items():
                if k not in log_obj:
                    log_obj[k] = v

        for attr in ("order_id", "payment_id", "product_id", "event_id", "event_type"):
            if hasattr(record, attr):
                log_obj[attr] = getattr(record, attr)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logger(service_name: str, log_level: str = "INFO") -> logging.Logger:
    service_name_ctx.set(service_name)
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
