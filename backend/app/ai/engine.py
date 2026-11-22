# backend/app/ai/engine.py
"""AI decision engine (PROTOTYPE).

Classifies citizen-submitted content into scam / genuine / complaint /
service_request with a confidence score, then routes:
  auto_handle   confidence >= 0.85 and no high-risk keyword
  ask_more_proof 0.60 <= confidence < 0.85
  human_handoff confidence < 0.60 or high-risk keyword present

Primary: Groq API (llama-3.3-70b-versatile) via the OpenAI-compatible SDK,
JSON mode, temperature 0. Backup: Google Gemini free tier.
Offline fallback: keyword heuristic so the demo never dies mid-judging.

The FULL reasoning trace is written to Decision.explanation_audit — that is
what GET /api/decisions/{id}/trace returns to the auditor.
"""
import json
import re

from ..config import settings

LABELS = ["scam", "genuine", "complaint", "service_request"]

URDU = {
    "scam": "یہ پیغام فراڈ لگ رہا ہے۔ کوئی بھی ادارہ آپ سے OTP یا PIN نہیں مانگتا۔ براہ کرم رقم نہ بھیجیں اور لنک نہ کھولیں۔",
    "genuine": "یہ پیغام درست معلوم ہوتا ہے۔ تاہم سرکاری ادارہ کسی بھی سرکاری ویب سائٹ سے تصدیق کر لیں۔",
    "complaint": "آپ کی شکایت درج کر لی گئی ہے۔ ہمارا نمائندہ جلد رابطہ کرے گا۔",
    "service_request": "یہ ایک سروس کی درخواست ہے۔ متعلقہ محکمے کو بھیج دی گئی ہے۔",
    "ask_more_proof": "مزید ثبوت کی ضرورت ہے۔ براہ کرم مکمل پیغام اسکرین شاٹ سمیت بھیجیں۔",
    "human_handoff": "یہ معاملہ ایک افسر کو بھیجا جا رہا ہے۔ وہ آپ سے رابطہ کرے گا۔",
}

SCAM_KEYWORDS = [
    "easypaisa", "jazzcash", "bisp", "ehsaas", "kamyab jawab", "prize", "jeet",
    "lottery", "muft", "bhej", "OTP".lower(), "verify your account", "urgent",
    "government grant", "cash reward", "click the link", "limited time",
]
GENUINE_HINTS = ["pakistan citizen portal", "complaint status", "tracking id", "helpline 0800"]
COMPLAINT_HINTS = ["complaint", "shikayat", "gifad", "broken", "not working", "delay"]
SERVICE_HINTS = ["request", "apply", "application", "duplicate", "certificate", "license renewal", "darakhwast"]


def _high_risk(text: str) -> list[str]:
    t = text.lower()
    return [kw for kw in settings.HIGH_RISK_KEYWORDS if kw in t]


def _heuristic_classify(text: str) -> dict:
    """Deterministic keyword fallback used when no AI provider is reachable."""
    t = text.lower()
    scam_hits = [k for k in SCAM_KEYWORDS if k in t]
    risk = _high_risk(text)
    genuine_hits = [k for k in GENUINE_HINTS if k in t]
    complaint_hits = [k for k in COMPLAINT_HINTS if k in t]
    service_hits = [k for k in SERVICE_HINTS if k in t]

    scores = {
        "scam": min(0.95, 0.45 + 0.15 * len(scam_hits) + (0.25 if risk else 0)),
        "genuine": min(0.9, 0.35 + 0.2 * len(genuine_hits)),
        "complaint": min(0.9, 0.35 + 0.15 * len(complaint_hits)),
        "service_request": min(0.9, 0.35 + 0.15 * len(service_hits)),
    }
    label = max(scores, key=scores.get)
    confidence = round(scores[label], 2)
    return {
        "label": label,
        "confidence": confidence,
        "signals": {
            "scam_keyword_hits": scam_hits,
            "high_risk_keywords": risk,
            "genuine_hint_hits": genuine_hits,
            "complaint_hint_hits": complaint_hits,
            "service_hint_hits": service_hits,
        },
        "engine": "heuristic",
    }


SYSTEM_PROMPT = (
    "You are the decision engine of Hifazat, a Pakistani scam-protection service. "
    "Classify the user-submitted message into exactly one of: "
    "scam, genuine, complaint, service_request. "
    "Reply ONLY with JSON: {\"label\": str, \"confidence\": number between 0 and 1, "
    "\"reasoning_en\": str, \"reasoning_ur\": str}. "
    "All data is fictional prototype data. Never include real personal data."
)


def _call_groq(openai_mod, text: str) -> dict:
    client = openai_mod.OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.GROQ_BASE_URL)
    resp = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify this submission:\n{text[:4000]}"},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def _call_gemini(openai_mod, text: str) -> dict:
    """Backup provider: Gemini free tier, also exposed as OpenAI-compatible."""
    client = openai_mod.OpenAI(
        api_key=settings.GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    resp = client.chat.completions.create(
        model="gemini-2.0-flash",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify this submission:\n{text[:4000]}"},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def ai_classify(text: str) -> dict:
    """Try Groq -> Gemini -> heuristic. Always returns a usable result dict."""
    attempts = []
    try:
        from openai import OpenAI as _O  # noqa: F401  (just checking availability)
        import openai as openai_mod
        if settings.GROQ_API_KEY:
            result = _call_groq(openai_mod, text)
            result["engine"] = f"groq:{settings.GROQ_MODEL}"
            return result
        if settings.GEMINI_API_KEY:
            result = _call_gemini(openai_mod, text)
            result["engine"] = "gemini:gemini-2.0-flash"
            return result
        attempts.append("no GROQ_API_KEY / GEMINI_API_KEY set; using offline heuristic")
    except Exception as exc:  # provider down / bad key / no network
        attempts.append(f"AI provider failed: {type(exc).__name__}: {exc}")

    fallback = _heuristic_classify(text)
    fallback["fallback_reason"] = "; ".join(attempts) or "provider unavailable"
    return fallback


def route_decision(confidence: float, text: str) -> tuple[str, list[str]]:
    """Pure routing rule (rule_version v1): returns (route, high_risk_keywords)."""
    risk = _high_risk(text)
    if risk or confidence < settings.ASK_MORE_PROOF_MIN:
        return "human_handoff", risk
    if confidence >= settings.AUTO_HANDLE_MIN:
        return "auto_handle", risk
    return "ask_more_proof", risk


def urdu_explanation(label: str, route: str) -> str:
    if route == "human_handoff":
        return URDU["human_handoff"] + " " + URDU.get(label, "")
    if route == "ask_more_proof":
        return URDU["ask_more_proof"]
    return URDU.get(label, URDU["ask_more_proof"])
