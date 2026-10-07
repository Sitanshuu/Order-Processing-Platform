from datetime import datetime, timezone
import uuid
from typing import Optional, Dict, Any
from pydantic import Field
from beanie import Document, Indexed


class NotificationDocument(Document):
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: Optional[str] = Indexed(default=None)
    recipient: str = Indexed()
    channel: str = "EMAIL"  # EMAIL, SMS
    template: str
    content: str
    status: str = "SENT"    # SENT, FAILED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = Indexed(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "notifications"
        indexes = [
            "order_id",
            "recipient",
            "correlation_id",
            "created_at",
        ]
