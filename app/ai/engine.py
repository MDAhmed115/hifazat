# backend/app/ai/engine.py
"""Orchestrator: pre_check -> classify -> route -> (RAG) -> explanation -> persist."""
import hashlib
import os
from datetime import datetime, timezone

from .classifier import classify, _call_groq, _extract_json, DEFAULT_MODEL
from .guardrails import pre_check, route_decision, officer_notes
from app.rules_engine import get_active_rules

PROMPT_VERSION = "p7-v1"

EXPL_SYSTEM = (
    "You write ONE very short, simple Urdu sentence and ONE short English sentence for an ordinary "
    "Pakistani citizen about a message they received. Use everyday words. NO technical words "
    "(no 'confidence', 'classifier', 'model', 'threshold'). Output ONLY JSON: "
    '{"urdu": "...", "english": "..."}'
)

STATIC_EXPL = {
    "scam": ("یہ پیغام دھوکہ لگتا ہے۔ کسی کو پیسے یا او ٹی پی نہ بھیجیں۔",
             "This message looks like a scam. Do not send money or any code."),
    "genuine": ("یہ پیغام ٹھیک لگتا ہے۔", "This message looks genuine."),
    "complaint": ("آپ کی شکایت درج کر لی گئی ہے۔", "Your complaint has been noted."),
    "service_request": ("آپ کی درخواست مل گئی ہے۔", "Your request has been received."),
    "human": ("ہم اس پیغام کو ایک افسر سے چیک کروا رہے ہیں۔ تب تک کوئی رقم نہ بھیجیں۔",
              "An officer is checking this message. Please do not send any money meanwhile."),
}


def make_explanation(label, route, reason_en):
    key = "human" if route == "human" else label
    static = STATIC_EXPL.get(key, STATIC_EXPL["human"])
    if route == "human":
        return {"urdu": static[0], "english": static[1]}
    try:
        msgs = [
            {"role": "system", "content": EXPL_SYSTEM},
            {"role": "user", "content": "Result: %s. Next step: %s. Note: %s" % (label, route, reason_en)},
        ]
        data = _extract_json(_call_groq(msgs))
        urdu, eng = str(data.get("urdu", "")).strip(), str(data.get("english", "")).strip()
        if urdu and eng:
            return {"urdu": urdu, "english": eng}
    except Exception:
        pass
    return {"urdu": static[0], "english": static[1]}


def decide_core(message_text, rules, rule_version_no):
    """Pure logic, no database. Returns the full decision dict."""
    now = datetime.now(timezone.utc).isoformat()
    sources = []
    pre = pre_check(message_text, rules)

    if pre is not None:
        result = {"label": "uncertain", "confidence": 0.0,
                  "extracted": {"sender": None, "amount": None, "account": None, "phone": None, "urls": []},
                  "red_flags": ["high-risk keywords: " + ", ".join(pre["matched"])],
                  "reason_en": "Contains high-risk words, sent to an officer without AI."}
        routing = {"route": "human", "reason": pre["reason"], "action": "officer_review", "follow_up": None}
        matched = pre["matched"]
        ai_used = False
    else:
        result = classify(message_text)
        routing = route_decision(result["label"], result["confidence"], rules)
        matched = []
        ai_used = True
        if result["label"] in ("genuine", "service_request"):
            try:
                from .rag import rag_query  # lazy: loads the heavy model only when needed
                sources = rag_query(message_text)["sources"]
                if not sources:  # retry with an English question written by the model (the embedding model is weak on Roman Urdu)
                    q = _extract_json(_call_groq([{"role": "system", "content": "Rewrite the citizen message as one short, clear English question. Reply with only a JSON object that has one key named q."}, {"role": "user", "content": message_text}])).get("q")
                    if q:
                        sources = rag_query(str(q))["sources"]
            except Exception:
                sources = []

    expl_user = make_explanation(result["label"], routing["route"], result["reason_en"])

    explanation_audit = {
        "input_hash": hashlib.sha256((message_text or "").encode("utf-8")).hexdigest(),
        "model": os.environ.get("GROQ_MODEL", DEFAULT_MODEL) if ai_used else "none (pre_check)",
        "model_version": "groq-api",
        "prompt_version": PROMPT_VERSION,
        "rule_version_no": rule_version_no,
        "confidence": result["confidence"],
        "label": result["label"],
        "route": routing["route"],
        "route_reason": routing["reason"],
        "matched_keywords": matched,
        "ai_called": ai_used,
        "timestamp": now,
    }
    return {**result, "route": routing["route"], "route_reason": routing["reason"],
            "action": routing["action"], "follow_up": routing["follow_up"],
            "matched_keywords": matched,
            "sources": sources,
            "explanation_user": expl_user, "explanation_audit": explanation_audit}


# ---- DB layer (adapted to the team's tables) ----
import re


def _db_route(route):
    """Our route names -> the names stored in the team's database.
    ASSUMPTION: the team's UI and seed use auto_handle / ask_more_proof / human_handoff."""
    return {"auto": "auto_handle", "ask_more": "ask_more_proof", "human": "human_handoff"}.get(route, route)


def _risk_level(route):
    if route == "human":
        return "high"
    if route == "ask_more":
        return "medium"
    return "low"


def _case_title(text, channel):
    clean = " ".join((text or "").split())[:80]
    if not clean:
        clean = "(no readable text)"
    return ("Document: " if channel == "document" else "") + clean


def _pattern_category(text):
    """Heuristic guess of the scam_patterns.category value."""
    low = (text or "").lower()
    if re.search(r"\b(otp|pin)\b", low):
        return "otp"
    if any(w in low for w in ("prize", "lucky draw", "lottery", "jeet gaye", "jeet liya")):
        return "lottery"
    if any(w in low for w in ("bisp", "ehsaas", "kafaalat", "kafalat", "relief", "qist", "benazir")):
        return "relief_payment"
    return "other"


def _pattern_language(text):
    """Heuristic: Urdu script -> 'ur', everything else -> 'en'."""
    return "ur" if any("\u0600" <= ch <= "\u06ff" for ch in (text or "")) else "en"


def decide(db, message_text, actor, case_id=None, extra_audit=None, channel="sms"):
    """Full pipeline with database. Returns the decision dict (with ids).

    extra_audit: optional dict merged into explanation_audit after decide_core runs
    (for example document OCR details). Heuristic data only, never proof.
    channel: sms / whatsapp / voice_transcript / document (stored on the message).
    Saves into the team's tables: cases, messages, decisions, scam_patterns, audit_log.
    """
    from app.audit import log_action
    from app.models import Case, Citizen, Decision, Message, ScamPattern

    rules, rule_id, rule_no = get_active_rules(db)
    out = decide_core(message_text, rules, rule_no)
    if extra_audit:
        out["explanation_audit"] = {**out["explanation_audit"], **extra_audit}

    internal_route = out["route"]
    db_route = _db_route(internal_route)

    case = db.get(Case, case_id) if case_id is not None else None
    case_created = False
    if case is None:
        citizen = (db.query(Citizen).filter(Citizen.user_id == actor.id)
                   .order_by(Citizen.id).first())                      # ASSUMPTION: first profile of this user
        case = Case(citizen_id=citizen.id if citizen else None, opened_by=actor.id,
                    title=_case_title(message_text, channel), status="open",
                    risk_level=_risk_level(internal_route))
        db.add(case)
        db.flush()
        case_created = True

    officer_note = None
    if internal_route == "human":
        case.status = "in_review"
        case.risk_level = "high"
        officer_note = officer_notes(out["matched_keywords"], out["confidence"], out["route_reason"])

    is_doc = channel == "document"
    msg = Message(case_id=case.id, channel=channel,
                  body_text=None if is_doc else message_text,
                  ocr_text=message_text if is_doc else None)
    db.add(msg)
    db.flush()

    # The decisions table has no columns for these, so they live in trace_json.
    trace = {
        **out["explanation_audit"],
        "message_id": msg.id,
        "db_route": db_route,
        "explanation_en": out["explanation_user"]["english"],
        "extracted": out["extracted"],
        "red_flags": out["red_flags"],
        "reason_en": out["reason_en"],
        "sources": out["sources"],
        "officer_notes": officer_note,
    }
    dec = Decision(case_id=case.id, label=out["label"], confidence=float(out["confidence"]),
                   route=db_route, explanation_ur=out["explanation_user"]["urdu"],
                   trace_json=trace, rule_version_id=rule_id)
    db.add(dec)
    db.flush()

    if out["label"] == "scam":
        snippet = (message_text or "")[:500]
        if snippet.strip() and db.query(ScamPattern).filter(ScamPattern.pattern_text == snippet).first() is None:
            db.add(ScamPattern(pattern_text=snippet, category=_pattern_category(snippet),
                               language=_pattern_language(snippet), severity=float(out["confidence"])))

    case_pk, msg_pk, dec_pk = case.id, msg.id, dec.id
    case_title, case_risk = case.title, case.risk_level
    db.commit()  # commit BEFORE log_action: log_action rolls back on its own failure

    if case_created:
        log_action(db, actor_id=actor.id, action="case.open", entity_type="cases", entity_id=case_pk,
                   details={"title": case_title, "risk_level": case_risk, "channel": channel})
    log_action(db, actor_id=actor.id, action="decision.made", entity_type="decisions", entity_id=dec_pk,
               details={"label": out["label"], "route": db_route, "rule_version": rule_no,
                        "channel": channel, "case_id": case_pk})

    return {"case_id": case_pk, "message_id": msg_pk, "decision_id": dec_pk,
            "rule_version_id": rule_id, "rule_version_no": rule_no,
            **out, "route": db_route, "internal_route": internal_route}
