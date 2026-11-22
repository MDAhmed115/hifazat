# backend/app/routers/analyze.py
"""Hifazat analysis endpoints.

POST /api/analyze           text message   -> decision engine
POST /api/analyze/document  png/jpg upload -> OCR -> heuristic forgery flags -> decision engine

Forgery flags are HEURISTICS ONLY, never proof.
"""
import os
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..ai.engine import decide
from ..ai.ocr import forgery_flags, ocr_image
from ..auth import require_role
from ..database import get_db
from ..models import Case, User

router = APIRouter(prefix="/api", tags=["analyze"])

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXT = {".png", ".jpg", ".jpeg"}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
# backend/uploads unless UPLOAD_DIR is set in the environment
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or (Path(__file__).resolve().parents[2] / "uploads"))


class AnalyzeIn(BaseModel):
    message_text: str = Field(max_length=5000)
    case_id: Optional[int] = None
    channel: Literal["sms", "whatsapp", "voice_transcript"] = "sms"


def _check_case_access(db: Session, case_id: Optional[int], user: User) -> None:
    if case_id is None:
        return
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    # ASSUMPTION: citizens may only add to their own cases; helpers may help with any case.
    if user.role == "citizen" and case.opened_by != user.id:
        raise HTTPException(status_code=403, detail="This case belongs to another user.")


# plain "def" (not async): FastAPI runs it in a thread, so the AI call does not block the server
@router.post("/analyze")
def analyze(
    body: AnalyzeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("citizen", "helper")),
):
    if not body.message_text.strip():
        raise HTTPException(status_code=400, detail="message_text is empty")
    _check_case_access(db, body.case_id, user)
    # label and confidence stay at the top level of the returned dict
    return decide(db, body.message_text, user, body.case_id, channel=body.channel)


# ======================= DOCUMENT OCR UPLOAD =======================
def _detect_image_type(data: bytes):
    """Look at the REAL file bytes, not the file name."""
    if data.startswith(PNG_MAGIC):
        return "png"
    if data.startswith(JPEG_MAGIC):
        return "jpeg"
    return None


@router.post("/analyze/document")
def analyze_document(
    file: UploadFile = File(...),
    case_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("citizen", "helper")),
):
    _check_case_access(db, case_id, user)

    # 1. Extension check (cheap, first)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Only png, jpg and jpeg images are allowed.")

    # 2. Size check: read at most MAX_BYTES + 1 so we know if it is too big
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is too large. Maximum size is 5 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    # 3. Real content check (magic numbers); it must also match the extension
    real_type = _detect_image_type(data)
    if real_type is None:
        raise HTTPException(status_code=400, detail="File content is not a real PNG or JPEG image.")
    if (real_type == "png") != (ext == ".png"):
        raise HTTPException(status_code=400, detail="File extension does not match the real image type.")

    # 4. Save under a random name (the uploaded file name is never used)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = uuid.uuid4().hex + (".png" if real_type == "png" else ".jpg")
    stored_path = UPLOAD_DIR / stored_name
    stored_path.write_bytes(data)

    # 5. OCR
    try:
        text = ocr_image(stored_path)
    except RuntimeError as e:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))

    # 6. Heuristic flags (NOT proof)
    flags = forgery_flags(text, str(stored_path))

    # 7. Same decision engine as text messages. Unreadable text still goes through;
    #    the engine routes low confidence to a human.
    extra_audit = {
        "source": "document_ocr",
        "forgery_flags": flags,
        "forgery_note": "heuristic flags only, not proof",
        "ocr_text_length": len(text),
        "stored_file": stored_name,
    }
    result = decide(db, text, user, case_id, extra_audit=extra_audit, channel="document")

    return {
        **result,
        "ocr_text": text,
        "forgery_flags": flags,
        "forgery_note": "heuristic flags only, not proof",
    }
