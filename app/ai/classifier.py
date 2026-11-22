# backend/app/ai/classifier.py
import json
import os
import re
import time
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from .prompts import build_messages

ALLOWED_LABELS = {"scam", "genuine", "complaint", "service_request", "uncertain"}
DEFAULT_MODEL = "openai/gpt-oss-120b"


class Extracted(BaseModel):
    sender: Optional[str] = None
    amount: Optional[str] = None
    account: Optional[str] = None
    phone: Optional[str] = None
    urls: List[str] = Field(default_factory=list)

    @field_validator("sender", "amount", "account", "phone", mode="before")
    @classmethod
    def _to_str(cls, v):
        if v is None or v == "":
            return None
        return str(v)

    @field_validator("urls", mode="before")
    @classmethod
    def _urls(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v]


class Decision(BaseModel):
    label: str = "uncertain"
    confidence: float = 0.3
    extracted: Extracted = Field(default_factory=Extracted)
    red_flags: List[str] = Field(default_factory=list)
    reason_en: str = ""

    @field_validator("label", mode="before")
    @classmethod
    def _label(cls, v):
        v = str(v).strip().lower().replace(" ", "_")
        return v if v in ALLOWED_LABELS else "uncertain"

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        try:
            v = float(v)
        except Exception:
            v = 0.3
        return max(0.0, min(1.0, v))

    @field_validator("red_flags", mode="before")
    @classmethod
    def _flags(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v]

    @field_validator("reason_en", mode="before")
    @classmethod
    def _reason(cls, v):
        return "" if v is None else str(v)


def _fallback(reason):
    d = Decision(label="uncertain", confidence=0.3, reason_en=reason)
    return d.model_dump()


def _extract_json(text):
    """Find the JSON object in the model reply, even if wrapped in ``` fences."""
    if not text:
        raise ValueError("empty reply")
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(text[start:end + 1])


def _call_groq(messages):
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing")
    client = Groq(api_key=api_key)
    r = client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", DEFAULT_MODEL),
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
        max_completion_tokens=2000,  # gpt-oss spends tokens on reasoning first
    )
    return r.choices[0].message.content


def classify(message_text):
    """Always returns a validated dict. NEVER raises."""
    try:
        text = (message_text or "").strip()
        if not text:
            return _fallback("Empty message.")

        last_error = "unknown error"
        for attempt in (1, 2):
            note = None if attempt == 1 else "Return ONLY valid JSON."
            try:
                raw = _call_groq(build_messages(text, note))
                data = _extract_json(raw)
                return Decision(**data).model_dump()
            except Exception as e:  # parse error, API error, rate limit...
                last_error = type(e).__name__ + ": " + str(e)[:150]
                time.sleep(1)
        return _fallback("AI could not produce a valid answer (" + last_error + "). Send to a human.")
    except Exception as e:  # absolute last safety net
        return _fallback("Classifier error: " + str(e)[:150])