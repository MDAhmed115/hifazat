# backend/app/routers/cases.py
"""Unified Case Management router combining P4 officer workflows with P5 consent gates and P6 AI triage."""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..ai import engine, rag
from ..audit import log_action
from ..database import get_db, utcnow
from ..deps import get_current_user, require_role
from ..models import Case, Citizen, Decision, Message, Notification, RuleVersion, User
from ..routers.consent import check_consent, log_data_access
from ..schemas import CaseCreate, CaseDetailOut, CaseIn, CaseOut, DecisionCreate, DecisionOut

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _case_to_out(c: Case) -> CaseOut:
    return CaseOut(
        id=c.id,
        citizen_id=c.citizen_id,
        channel=c.channel,
        status=c.status,
        title=c.title,
        priority=c.priority,
        risk_level=c.risk_level,
        created_at=c.created_at,
    )


def _decision_to_out(d: Decision) -> DecisionOut:
    return DecisionOut(
        id=d.id,
        case_id=d.case_id,
        label=d.label,
        confidence=d.confidence,
        route=d.route,
        rule_version_id=d.rule_version_id,
        explanation_ur=d.explanation_ur,
        explanation_user=d.explanation_user or d.explanation_ur,
        decided_by=d.decided_by,
    )


# ----------------------------------------------------------------------
# 1. Create Case
# ----------------------------------------------------------------------
@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    current_user: User = Depends(require_role("citizen", "helper", "officer", "admin")),
    db: Session = Depends(get_db),
):
    """Create a new scam report case with attached initial message."""
    citizen_id = payload.citizen_id
    if current_user.role == "citizen":
        cit = db.query(Citizen).filter(Citizen.user_id == current_user.id).first()
        citizen_id = cit.id if cit else None

    case = Case(
        citizen_id=citizen_id,
        opened_by=current_user.id,
        title=payload.title or "Suspicious Message",
        type=payload.type,
        channel=payload.channel,
        status="open",
        priority=payload.priority,
    )
    db.add(case)
    db.flush()

    raw_msg = payload.raw_text or payload.body_text or ""
    if raw_msg:
        msg = Message(
            case_id=case.id,
            channel=payload.channel,
            sender_number=payload.sender_number,
            sender_role=current_user.role,
            body_text=raw_msg,
            raw_text=raw_msg,
        )
        db.add(msg)

    db.commit()
    db.refresh(case)

    log_action(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="case.created",
        entity_type="case",
        entity_id=case.id,
        details={"title": case.title, "channel": case.channel, "priority": case.priority},
    )
    return _case_to_out(case)


# ----------------------------------------------------------------------
# 2. Officer Queue (Sorted by Priority DESC)
# ----------------------------------------------------------------------
@router.get("/queue", response_model=List[CaseOut])
def officer_queue(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role("officer", "admin")),
    db: Session = Depends(get_db),
):
    """Officer queue sorted by priority DESC and creation time ASC."""
    cases = (
        db.query(Case)
        .filter(Case.status.in_(["open", "in_review", "with_officer"]))
        .order_by(desc(Case.priority), Case.created_at.asc())
        .limit(limit)
        .all()
    )
    # Filter out cases where citizen has withdrawn consent
    visible_cases = []
    for c in cases:
        if c.citizen_id:
            try:
                check_consent(db, c.citizen_id, current_user.role)
                visible_cases.append(c)
            except HTTPException:
                continue
        else:
            visible_cases.append(c)

    return [_case_to_out(c) for c in visible_cases]


# ----------------------------------------------------------------------
# 3. List Cases (Role-Aware + Consent-Gated)
# ----------------------------------------------------------------------
@router.get("", response_model=List[CaseOut])
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List cases visible to the caller (citizen: own cases; officer/admin/auditor: all non-withdrawn)."""
    q = db.query(Case)

    if current_user.role == "citizen":
        cit = db.query(Citizen).filter(Citizen.user_id == current_user.id).first()
        if not cit:
            return []
        q = q.filter(Case.citizen_id == cit.id)
    elif current_user.role == "helper":
        citizens = db.query(Citizen).filter(Citizen.helper_id == current_user.id).all()
        cit_ids = [c.id for c in citizens]
        q = q.filter(Case.citizen_id.in_(cit_ids))

    if status_filter:
        q = q.filter(Case.status == status_filter)

    cases = q.order_by(desc(Case.id)).all()

    # Apply consent gate for officers/helpers/admins
    result = []
    for c in cases:
        if c.citizen_id and current_user.role not in ("citizen", "auditor"):
            try:
                check_consent(db, c.citizen_id, current_user.role)
                result.append(c)
            except HTTPException:
                continue
        else:
            result.append(c)

    return [_case_to_out(c) for c in result]


# ----------------------------------------------------------------------
# 4. Get Case Detail (Gated by check_consent & log_data_access)
# ----------------------------------------------------------------------
@router.get("/{case_id}", response_model=CaseDetailOut)
def get_case(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full case details including messages and decision. Enforces strict consent gate."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Consent Check: if citizen withdrew consent, non-citizens get 403
    if case.citizen_id:
        check_consent(db, case.citizen_id, current_user.role)
        if current_user.role != "citizen":
            log_data_access(db, current_user, case.citizen_id, f"case_{case_id}")

    # Citizen ownership check
    if current_user.role == "citizen":
        cit = db.query(Citizen).filter(Citizen.user_id == current_user.id).first()
        if cit and case.citizen_id != cit.id:
            raise HTTPException(status_code=403, detail="Forbidden")

    # Latest decision
    dec = (
        db.query(Decision)
        .filter(Decision.case_id == case.id)
        .order_by(desc(Decision.id))
        .first()
    )

    # Messages
    msgs = [
        {
            "id": m.id,
            "channel": m.channel,
            "sender_role": m.sender_role,
            "body": m.body,
            "created_at": str(m.created_at),
        }
        for m in case.messages
    ]

    return CaseDetailOut(
        case=_case_to_out(case),
        messages=msgs,
        decision=_decision_to_out(dec) if dec else None,
    )


# ----------------------------------------------------------------------
# 5. Escalate Case
# ----------------------------------------------------------------------
@router.post("/{case_id}/escalate", response_model=CaseOut)
def escalate_case(
    case_id: int,
    current_user: User = Depends(require_role("helper", "officer", "admin")),
    db: Session = Depends(get_db),
):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = "with_officer"
    case.priority = min(10, case.priority + 3)
    case.updated_at = utcnow()
    db.commit()

    log_action(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="case.escalated",
        entity_type="case",
        entity_id=case.id,
        details={"new_priority": case.priority},
    )
    return _case_to_out(case)


# ----------------------------------------------------------------------
# 6. Assign Case
# ----------------------------------------------------------------------
@router.post("/{case_id}/assign", response_model=CaseOut)
def assign_case(
    case_id: int,
    officer_id: int = Query(...),
    current_user: User = Depends(require_role("officer", "admin")),
    db: Session = Depends(get_db),
):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    officer = db.get(User, officer_id)
    if not officer or officer.role != "officer":
        raise HTTPException(status_code=400, detail="Invalid officer id")

    case.assigned_officer_id = officer.id
    case.status = "in_review"
    case.updated_at = utcnow()
    db.commit()

    log_action(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="case.assigned",
        entity_type="case",
        entity_id=case.id,
        details={"officer_id": officer.id},
    )
    return _case_to_out(case)


# ----------------------------------------------------------------------
# 7. Decide Case (Manual Officer or Automated AI)
# ----------------------------------------------------------------------
@router.post("/{case_id}/decide", response_model=DecisionOut)
def decide_case(
    case_id: int,
    payload: Optional[DecisionCreate] = None,
    current_user: User = Depends(require_role("officer", "admin")),
    db: Session = Depends(get_db),
):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # If payload is provided, use officer's decision
    if payload:
        dec = Decision(
            case_id=case.id,
            label=payload.label,
            confidence=payload.confidence,
            route=payload.route,
            explanation_ur=payload.explanation_ur or "",
            explanation_user=payload.explanation_user or payload.explanation_ur,
            explanation_audit=payload.explanation_audit or {},
            sources=payload.sources or {},
            decided_by=payload.decided_by or current_user.name or "officer",
        )
    else:
        # Run AI classification on latest case message
        text = case.raw_content or ""
        if case.messages:
            text = case.messages[-1].body
        ai_res = engine.ai_classify(text)
        route_info = engine.route_decision(ai_res["confidence"], ai_res["label"], text)

        dec = Decision(
            case_id=case.id,
            label=ai_res["label"],
            confidence=ai_res["confidence"],
            route=route_info["route"],
            explanation_ur=ai_res.get("explanation_ur", ""),
            explanation_user=ai_res.get("explanation_ur", ""),
            explanation_audit={
                "model": ai_res.get("model", "engine_v1"),
                "reasoning": ai_res.get("reasoning", ""),
                "risk_keywords": route_info.get("risk_keywords", []),
            },
            sources={},
            decided_by="ai_rule_engine",
        )

    db.add(dec)
    case.status = "resolved" if dec.route == "auto_handle" else "in_review"
    case.updated_at = utcnow()
    db.commit()
    db.refresh(dec)

    log_action(
        db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="decision.recorded",
        entity_type="decision",
        entity_id=dec.id,
        details={"label": dec.label, "confidence": dec.confidence, "route": dec.route},
    )
    return _decision_to_out(dec)


# ----------------------------------------------------------------------
# 8. Case Audit Trail
# ----------------------------------------------------------------------
@router.get("/{case_id}/audit")
def case_audit_trail(
    case_id: int,
    current_user: User = Depends(require_role("officer", "admin", "auditor")),
    db: Session = Depends(get_db),
):
    """View all audit log events recorded for this case."""
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
