# backend/app/routers/decision_routes.py
"""Decision endpoint: the AI engine classifies a case, persists the decision
with the full auditor trace, and routes it (auto_handle / ask_more_proof /
human_handoff). Called after a citizen submits a case."""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..ai import engine, rag
from ..audit import log_action
from ..config import settings
from ..database import SessionLocal, get_db, utcnow
from ..models import Case, Citizen, Decision, Notification, RuleVersion, User
from ..security import get_current_user

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


def run_decision_background(case_id: int) -> None:
    """Background worker: classify + persist decision + audit log + notify."""
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        if case is None:
            return

        text = case.raw_content or ""
        if not text and case.messages:
            text = case.messages[-1].body

        rv = db.query(RuleVersion).filter(RuleVersion.active.is_(True)).first()
        auto_min = (rv.thresholds or {}).get("auto", settings.AUTO_HANDLE_MIN) if rv else settings.AUTO_HANDLE_MIN
        ask_min = (rv.thresholds or {}).get("ask", settings.ASK_MORE_PROOF_MIN) if rv else settings.ASK_MORE_PROOF_MIN

        result = engine.ai_classify(text)
        label = result.get("label")
        if label not in engine.LABELS:
            label, result = "scam", engine._heuristic_classify(text)
        confidence = float(result.get("confidence", 0.0))
        route, risk_kws = engine.route_decision(confidence, text)

        sources = {"rag_matches": rag.retrieve_similar(text), "ocr_used": False}

        explanation_audit = {
            "engine": result.get("engine", "unknown"),
            "model_version": result.get("engine", "heuristic"),
            "fallback_reason": result.get("fallback_reason"),
            "label": label,
            "confidence": confidence,
            "reasoning_en": result.get("reasoning_en", ""),
            "reasoning_ur": result.get("reasoning_ur", ""),
            "signals": result.get("signals", {}),
            "high_risk_keywords": risk_kws,
            "thresholds_applied": {"auto_handle_min": auto_min, "ask_more_proof_min": ask_min},
            "routing_rule": (
                "human_handoff if high_risk_keyword or confidence<ask_min; "
                "auto_handle if confidence>=auto_min; else ask_more_proof"
            ),
            "decision_timestamp": utcnow().isoformat(),
            "case_channel": case.channel,
            "content_length": len(text),
        }

        dec = Decision(
            case_id=case.id,
            label=label,
            confidence=confidence,
            route=route,
            explanation_ur=engine.urdu_explanation(label, route),
            explanation_user=engine.urdu_explanation(label, route),
            explanation_audit=explanation_audit,
            sources=sources,
            rule_version_id=rv.id if rv else None,
            decided_by="ai_rule_engine",
        )
        db.add(dec)
        db.flush()

        status_map = {
            "auto_handle": "auto_handled",
            "ask_more_proof": "needs_proof",
            "human_handoff": "human_review",
        }
        case.status = status_map.get(route, "in_review")
        case.updated_at = utcnow()

        cit = db.get(Citizen, case.citizen_id)
        if cit is not None and cit.user_id:
            db.add(Notification(
                user_id=cit.user_id,
                case_id=case.id,
                title=f"Decision: {label}",
                body=dec.explanation_ur,
            ))

        log_action(
            db,
            actor_id=None,
            actor_role="ai_engine",
            action="decision_recorded",
            entity_type="decision",
            entity_id=dec.id,
            details={"case_id": case.id, "label": label, "confidence": confidence, "route": route},
        )
        db.commit()
    finally:
        db.close()


@router.post("/cases/{case_id}/queue", status_code=status.HTTP_202_ACCEPTED)
def queue_case_decision(
    case_id: int,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger the AI decision background worker for a case."""
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Case not found")

    background.add_task(run_decision_background, case_id)
    return {"detail": "decision queued", "case_id": case_id}
