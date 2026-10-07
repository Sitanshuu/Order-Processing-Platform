from typing import Optional, List
from fastapi import APIRouter, Query, Path
from services.audit_service.documents import AuditEventDocument

router = APIRouter(prefix="/api/v1/audit", tags=["Audit & Event Store"])


@router.get("/events", response_model=List[dict])
async def list_audit_events(
    correlation_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    source_service: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    query = {}
    if correlation_id:
        query["correlation_id"] = correlation_id
    if event_type:
        query["event_type"] = event_type
    if source_service:
        query["source_service"] = source_service

    docs = await AuditEventDocument.find(query).sort("-ingested_at").limit(limit).to_list()
    return [
        {
            "event_id": d.event_id,
            "event_type": d.event_type,
            "event_version": d.event_version,
            "source_service": d.source_service,
            "correlation_id": d.correlation_id,
            "causation_id": d.causation_id,
            "payload": d.payload,
            "occurred_at": d.occurred_at,
            "ingested_at": d.ingested_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/trace/{correlation_id}", response_model=List[dict])
async def get_distributed_trace(
    correlation_id: str = Path(..., description="Distributed Correlation ID to reconstruct chronological lifecycle"),
):
    """
    Reconstructs the end-to-end chronological timeline of all events across all microservices
    for a specific distributed transaction.
    """
    docs = await AuditEventDocument.find(AuditEventDocument.correlation_id == correlation_id).sort("+ingested_at").to_list()
    return [
        {
            "step": idx + 1,
            "event_id": d.event_id,
            "event_type": d.event_type,
            "source_service": d.source_service,
            "correlation_id": d.correlation_id,
            "causation_id": d.causation_id,
            "payload": d.payload,
            "occurred_at": d.occurred_at,
            "ingested_at": d.ingested_at.isoformat(),
        }
        for idx, d in enumerate(docs)
    ]
