# backend/app/audit.py
"""Unified audit logging helper."""
import json
from typing import Any, Optional
from sqlalchemy.orm import Session

from .models import AuditLog


def log_action(
    db: Session,
    actor_id: Optional[int] = None,
    action: str = "",
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    details: Optional[dict] = None,
    actor_role: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    entity: Optional[str] = None,
    detail: Optional[dict] = None,
) -> Optional[AuditLog]:
    """Write an audit_log row and commit immediately. Swallows exceptions so audit never crashes main operations."""
    try:
        resolved_actor_id = actor_id if actor_id is not None else actor_user_id
        resolved_entity = entity_type or entity or "system"
        resolved_details = details if details is not None else (detail or {})

        row = AuditLog(
            actor_id=resolved_actor_id,
            actor_role=actor_role or "citizen",
            action=action,
            entity_type=resolved_entity,
            entity=resolved_entity,
            entity_id=entity_id,
            details=json.dumps(resolved_details, ensure_ascii=False, default=str),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        return None
