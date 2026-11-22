# backend/app/routers/audit_routes.py
"""Auditor read-only endpoints: audit log, decision traces, consent event records."""
import datetime as dt
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Consent, Decision, RuleVersion, User
from ..schemas import AuditPage, ConsentRecordOut, DecisionTraceOut
from ..security import require_role

router = APIRouter(prefix="/api", tags=["audit"])


def _parse_date(value: str, field: str) -> dt.datetime:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field} '{value}', expected YYYY-MM-DD",
        )


# ----------------------------------------------------------------------
# 1. GET /api/audit (Paginated Audit Log)
# ----------------------------------------------------------------------
@router.get("/audit", response_model=AuditPage)
def list_audit_log(
    action: Optional[str] = Query(None, description="exact action, e.g. case.created"),
    entity_type: Optional[str] = Query(None, description="exact entity, e.g. case"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_role("auditor")),
    db: Session = Depends(get_db),
):
    """Paginated audit_log, newest first. Enforces read-only guarantee for auditors."""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter((AuditLog.entity_type == entity_type) | (AuditLog.entity == entity_type))
    if date_from:
        q = q.filter(AuditLog.created_at >= _parse_date(date_from, "date_from"))
    if date_to:
        q = q.filter(AuditLog.created_at < _parse_date(date_to, "date_to") + dt.timedelta(days=1))

    total = q.count()
    rows = (
        q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditPage(items=rows, total=total, page=page, page_size=page_size)


# ----------------------------------------------------------------------
# 2. GET /api/decisions/{id}/trace (Full Decision Trace)
# ----------------------------------------------------------------------
@router.get("/decisions/{decision_id}/trace", response_model=DecisionTraceOut)
def decision_trace(
    decision_id: int,
    _: User = Depends(require_role("auditor", "officer")),
    db: Session = Depends(get_db),
):
    """Full explanation_audit JSON + sources + rule_version used, for one decision."""
    dec = db.get(Decision, decision_id)
    if dec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Decision not found")

    rule_version = None
    if dec.rule_version_id is not None:
        rv = db.get(RuleVersion, dec.rule_version_id)
        if rv is not None:
            rule_version = {
                "id": rv.id,
                "version": rv.version,
                "description": rv.description,
                "thresholds": rv.thresholds,
                "active": rv.active,
            }

    return DecisionTraceOut(
        id=dec.id,
        case_id=dec.case_id,
        label=dec.label,
        confidence=dec.confidence,
        route=dec.route,
        explanation_ur=dec.explanation_ur,
        explanation_audit=dec.explanation_audit or {},
        sources=dec.sources or {},
        rule_version=rule_version,
        decided_by=dec.decided_by,
        created_at=dec.created_at,
    )


# ----------------------------------------------------------------------
# 3. GET /api/consent/records (Chronological Consent Event Records)
# ----------------------------------------------------------------------
@router.get("/consent/records", response_model=List[ConsentRecordOut])
def consent_records(
    _: User = Depends(require_role("auditor")),
    db: Session = Depends(get_db),
):
    """All consent events (grants, sharing updates, revocations), newest first."""
    return db.query(Consent).order_by(Consent.granted_at.desc(), Consent.id.desc()).all()


# ----------------------------------------------------------------------
# 4. GET /api/audit/cases/{case_id}/trail (P4 Case Specific Audit Trail)
# ----------------------------------------------------------------------
@router.get("/audit/cases/{case_id}/trail")
def case_audit_trail_alias(
    case_id: int,
    _: User = Depends(require_role("auditor", "officer", "admin")),
    db: Session = Depends(get_db),
):
    """Audit trail for a specific case."""
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "case", AuditLog.entity_id == case_id)
        .order_by(AuditLog.id.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "action": r.action,
            "actor_role": r.actor_role,
            "detail": r.detail,
            "created_at": str(r.created_at),
        }
        for r in rows
    ]
