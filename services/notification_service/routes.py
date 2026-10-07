from typing import Optional, List
from fastapi import APIRouter, Query
from services.notification_service.documents import NotificationDocument

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("", response_model=List[dict])
async def list_notifications(
    order_id: Optional[str] = Query(None),
    recipient: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    query = {}
    if order_id:
        query["order_id"] = order_id
    if recipient:
        query["recipient"] = recipient

    docs = await NotificationDocument.find(query).sort("-created_at").limit(limit).to_list()
    return [
        {
            "id": str(d.id),
            "notification_id": d.notification_id,
            "order_id": d.order_id,
            "recipient": d.recipient,
            "channel": d.channel,
            "template": d.template,
            "content": d.content,
            "status": d.status,
            "created_at": d.created_at.isoformat(),
            "correlation_id": d.correlation_id,
        }
        for d in docs
    ]
