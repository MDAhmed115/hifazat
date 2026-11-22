# backend/app/routers/consent.py
"""Consent management router combining P5 (lifecycle/sharing/withdrawal) and P6 (event tracking)."""
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import log_action
from ..database import get_db, utcnow
from ..deps import get_own_citizen
from ..models import AuditLog, Case, Citizen, Consent, Decision, User
from ..schemas import (
    AccessEntry,
    AccessSummary,
    ConsentDetailOut,
    ConsentIn,
    ConsentOut,
    ConsentRecordOut,
    SharingUpdateIn,
)
from ..security import get_current_user, require_role

router = APIRouter(prefix="/api/consent", tags=["consent"])

SHARABLE_ROLES = {"officer", "helper"}


# ---------- Shared Helpers ----------
def _load_shared_with(consent: Consent) -> list[str]:
    try:
        val = json.loads(consent.shared_with)
        return val if isinstance(val, list) else []
    except (TypeError, ValueError):
        return []


def _consent_to_out(consent: Consent) -> ConsentOut:
    return ConsentOut(
        sharing_enabled=consent.sharing_enabled,
        shared_with=_load_shared_with(consent),
        version=consent.version,
        granted_at=consent.granted_at,
        updated_at=consent.updated_at,
        withdrawn_at=consent.withdrawn_at,
    )


def check_consent(db: Session, citizen_id: int, viewer_role: str) -> None:
    """Raise 403 'User has withdrawn consent' if viewer tries to read data of a withdrawn citizen."""
    if viewer_role in ("citizen", "auditor"):
        return
    consent = db.query(Consent).filter(Consent.citizen_id == citizen_id).first()
    if consent is None:
        return
    if not consent.sharing_enabled or consent.withdrawn_at is not None:
        raise HTTPException(status_code=403, detail="User has withdrawn consent")


def log_data_access(db: Session, viewer: User, citizen_id: int, resource: str) -> None:
    """Record access events for the citizen's transparency log."""
    try:
        log_action(
            db,
            actor_id=viewer.id,
            actor_role=viewer.role,
            action="view",
            entity_type="citizen_data",
            entity="citizen_data",
            entity_id=citizen_id,
            details={"resource": resource},
        )
    except Exception:
        db.rollback()


# ---------- Endpoints ----------
@router.get("", response_model=ConsentDetailOut)
def get_my_consent(
    pair: tuple[User, Citizen] = Depends(get_own_citizen),
    db: Session = Depends(get_db),
) -> ConsentDetailOut:
    """Current consent record + summary of who accessed my data."""
    user, citizen = pair
    consent = db.query(Consent).filter(Consent.citizen_id == citizen.id).first()
    if consent is None:
        consent = Consent(
            citizen_id=citizen.id,
            sharing_enabled=True,
            shared_with='["helper"]',
            version=1,
        )
        db.add(consent)
        db.commit()
        db.refresh(consent)

    rows = (
        db.query(
            AuditLog.actor_role,
            func.count(AuditLog.id),
            func.max(AuditLog.created_at),
        )
        .filter(AuditLog.entity == "citizen_data", AuditLog.entity_id == citizen.id)
        .group_by(AuditLog.actor_role)
        .all()
    )

    by_role = [
        AccessEntry(actor_role=role, count=int(cnt), last_at=last_at, actions=["view"])
        for role, cnt, last_at in rows
        if role != "citizen"
    ]
    total = sum(e.count for e in by_role)

    return ConsentDetailOut(
        consent=_consent_to_out(consent),
        who_accessed=AccessSummary(citizen_id=citizen.id, total_access_events=total, by_role=by_role),
    )


@router.patch("/sharing", response_model=ConsentOut)
def update_sharing(
    payload: SharingUpdateIn,
    pair: tuple[User, Citizen] = Depends(get_own_citizen),
    db: Session = Depends(get_db),
) -> ConsentOut:
    """Update roles citizen agrees to share case data with."""
    user, citizen = pair
    invalid = [r for r in payload.shared_with if r not in SHARABLE_ROLES]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Only 'officer' and 'helper' can be shared with; got {invalid}",
        )

    consent = db.query(Consent).filter(Consent.citizen_id == citizen.id).first()
    if consent is None:
        raise HTTPException(status_code=404, detail="No consent record for this citizen")
    if consent.withdrawn_at is not None or not consent.sharing_enabled:
        raise HTTPException(status_code=409, detail="Consent already withdrawn; cannot update sharing")

    old = _load_shared_with(consent)
    consent.shared_with = json.dumps(sorted(payload.shared_with))
    consent.version += 1
    consent.updated_at = utcnow()
    db.commit()
    db.refresh(consent)

    log_action(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="consent_sharing_updated",
        entity_type="consent",
        entity="consent",
        entity_id=consent.id,
        details={"citizen_id": citizen.id, "from": old, "to": sorted(payload.shared_with), "version": consent.version},
    )
    return _consent_to_out(consent)


@router.post("/withdraw", response_model=ConsentOut)
def withdraw_consent(
    pair: tuple[User, Citizen] = Depends(get_own_citizen),
    db: Session = Depends(get_db),
) -> ConsentOut:
    """Withdraw all consent: freezes access, redacts explanation_audit, blocks future officer reads."""
    user, citizen = pair
    consent = db.query(Consent).filter(Consent.citizen_id == citizen.id).first()
    if consent is None:
        raise HTTPException(status_code=404, detail="No consent record for this citizen")
    if consent.withdrawn_at is not None:
        raise HTTPException(status_code=409, detail="Consent already withdrawn")

    consent.sharing_enabled = False
    consent.withdrawn_at = utcnow()
    consent.shared_with = "[]"
    consent.version += 1
    db.flush()

    # Redact AI explanation_audit artifacts on all this citizen's cases
    case_ids = [c.id for c in db.query(Case).filter(Case.citizen_id == citizen.id).all()]
    redacted_count = 0
    if case_ids:
        decisions = db.query(Decision).filter(Decision.case_id.in_(case_ids)).all()
        for dec in decisions:
            dec.explanation_audit = {"redacted": True}
            redacted_count += 1

    db.commit()
    db.refresh(consent)

    log_action(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="consent_withdrawn",
        entity_type="consent",
        entity="consent",
        entity_id=consent.id,
        details={
            "citizen_id": citizen.id,
            "cases_kept": len(case_ids),
            "decisions_redacted": redacted_count,
            "version": consent.version,
        },
    )
    return _consent_to_out(consent)


@router.post("", status_code=201)
def set_consent_event(
    payload: ConsentIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Event-based consent grant/revocation with hashed IP logging (P6 compatibility)."""
    cit = db.query(Citizen).filter(Citizen.user_id == user.id).first()
    if cit is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only citizens have consent records")

    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()

    if payload.granted:
        row = Consent(
            citizen_id=cit.id,
            consent_type=payload.consent_type,
            granted=True,
            sharing_enabled=True,
            ip_hash=ip_hash,
        )
        db.add(row)
        db.commit()
        log_action(
            db,
            actor_id=user.id,
            actor_role=user.role,
            action="consent_granted",
            entity_type="consent",
            entity_id=row.id,
            details={"consent_type": payload.consent_type},
        )
    else:
        latest = (
            db.query(Consent)
            .filter(Consent.citizen_id == cit.id, Consent.consent_type == payload.consent_type, Consent.granted.is_(True))
            .order_by(Consent.id.desc())
            .first()
        )
        if latest is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No active consent of that type")
        latest.revoked_at = utcnow()
        latest.sharing_enabled = False
        db.commit()
        log_action(
            db,
            actor_id=user.id,
            actor_role=user.role,
            action="consent_revoked",
            entity_type="consent",
            entity_id=latest.id,
            details={"consent_type": payload.consent_type},
        )

    return {"detail": "ok"}


@router.get("/records", response_model=List[ConsentRecordOut])
def list_consent_records(
    _: User = Depends(require_role("auditor")),
    db: Session = Depends(get_db),
):
    """Auditor-only view of all consent events."""
    return db.query(Consent).order_by(Consent.granted_at.desc(), Consent.id.desc()).all()
