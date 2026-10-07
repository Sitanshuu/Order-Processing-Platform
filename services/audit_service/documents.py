from datetime import datetime, timezone
import uuid
from typing import Optional, Dict, Any
from pydantic import Field
from beanie import Document, Indexed


class AuditEventDocument(Document):
    event_id: str = Indexed(unique=True)
    event_type: str = Indexed()
    event_version: int = 1
    source_service: str = Indexed()
    correlation_id: str = Indexed()
    causation_id: Optional[str] = Indexed(default=None)
    payload: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "audit_events"
        indexes = [
            "event_id",
            "event_type",
            "correlation_id",
            "source_service",
            "ingested_at",
        ]
