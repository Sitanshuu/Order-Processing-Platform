from typing import Optional, Dict, Any
from pydantic import BaseModel
from shared.events.base import DomainEvent


class NotificationSentPayload(BaseModel):
    notification_id: str
    order_id: Optional[str] = None
    recipient: str
    channel: str  # EMAIL / SMS
    template: str
    sent_at: str
    status: str = "SENT"
    metadata: Dict[str, Any] = {}


def create_notification_sent_event(
    notification_id: str,
    recipient: str,
    channel: str,
    template: str,
    sent_at: str,
    correlation_id: str,
    causation_id: str,
    order_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> DomainEvent:
    return DomainEvent(
        event_type="NotificationSent",
        source="notification-service",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=NotificationSentPayload(
            notification_id=notification_id,
            order_id=order_id,
            recipient=recipient,
            channel=channel,
            template=template,
            sent_at=sent_at,
            metadata=metadata or {},
        ).model_dump(),
    )
