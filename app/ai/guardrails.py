# backend/app/ai/guardrails.py
"""Safety layer: keyword pre-check + asymmetric routing."""
import re

FOLLOW_UP = {
    "scam": "Did the message ask you to send any money first?",
    "genuine": "Do you have a reference number?",
    "complaint": "Since when have you not received your payment, and what is your CNIC's last 4 digits?",
    "service_request": "Which relief scheme are you asking about?",
    "uncertain": "Can you share the full message, or a photo of it?",
}


def _kw_pattern(kw):
    kw = kw.strip().lower()
    if not kw:
        return None
    escaped = re.escape(kw)
    if re.fullmatch(r"[a-z0-9 ]+", kw):
        return re.compile(r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])", re.IGNORECASE)
    return re.compile(escaped)


def pre_check(message_text, rules=None):
    """Return a human route if any high-risk keyword is in the text, else None."""
    if rules is None:
        from app.rules_engine import default_rules
        rules = default_rules()
    text = (message_text or "").lower()
    text = re.sub(r"\s+", " ", text)
    matched = []
    for kw in rules.get("high_risk_keywords", []):
        pat = _kw_pattern(kw)
        if pat is not None and pat.search(text):
            matched.append(kw)
    if matched:
        return {"route": "human", "reason": "high_risk_keywords", "matched": matched}
    return None


def route_decision(label, confidence, rules):
    """Asymmetric routing.

    ASSUMED COSTS (PKR): wrong approval (scam called genuine) = 25,000;
    wrong rejection (genuine called scam) = 2,000.
    Break-even error rate = 2,000 / (2,000 + 25,000) = 7.4%, so auto-approve
    only at confidence >= ~0.926. Hence genuine threshold (0.90) is stricter
    than scam threshold (0.85).
    """
    label = (label or "uncertain").lower()
    c = float(confidence)
    t_scam = float(rules["auto_scam_threshold"])
    t_gen = float(rules["auto_genuine_threshold"])
    t_human = float(rules["human_threshold"])

    if label == "uncertain" or c < t_human:
        return {"route": "human", "reason": "low_confidence_or_uncertain", "action": "officer_review", "follow_up": None}

    if label == "scam":
        if c >= t_scam:
            return {"route": "auto", "reason": "confident_scam", "action": "warn_and_offer_report", "follow_up": None}
        return {"route": "ask_more", "reason": "scam_not_certain", "action": "ask_follow_up", "follow_up": FOLLOW_UP["scam"]}

    if label == "genuine":
        if c >= t_gen:
            return {"route": "auto", "reason": "confident_genuine", "action": "proceed", "follow_up": None}
        return {"route": "ask_more", "reason": "genuine_not_certain", "action": "ask_follow_up", "follow_up": FOLLOW_UP["genuine"]}

    if c >= t_scam:
        return {"route": "auto", "reason": "confident_" + label, "action": "log_and_respond", "follow_up": None}
    return {"route": "ask_more", "reason": label + "_not_certain", "action": "ask_follow_up",
            "follow_up": FOLLOW_UP.get(label, FOLLOW_UP["uncertain"])}


def officer_notes(matched, confidence, reason):
    kw = ", ".join(matched) if matched else "none"
    return "HUMAN REVIEW. Matched keywords: %s. Confidence: %.2f. Reason: %s. Do not auto-act." % (kw, confidence, reason)
