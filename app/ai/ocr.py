# app/ai/ocr.py
"""
Document OCR + heuristic forgery flags for Hifazat.

IMPORTANT HONESTY NOTE:
forgery_flags() uses simple HEURISTICS only. A flag means "this looks odd and a
human should look at it". NO flag does NOT mean the document is genuine, and a
flag does NOT prove forgery. Never present these as proof to a user.
"""
import os
import re
import shutil
from datetime import date
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional here
    pass

FORGERY_NOTE = "Heuristic flags only, not proof."

WINDOWS_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_lang_cache = None


# --------------------------------------------------------------------------
# OCR
# --------------------------------------------------------------------------
def _configure_tesseract():
    """Find tesseract: env var TESSERACT_CMD, then PATH, then the Windows default."""
    env_cmd = os.getenv("TESSERACT_CMD")
    if env_cmd:
        if Path(env_cmd).exists():
            pytesseract.pytesseract.tesseract_cmd = env_cmd
            return
        raise RuntimeError(
            "TESSERACT_CMD is set to '" + env_cmd + "' but that file does not exist. "
            "Fix the path in .env or remove the variable."
        )

    on_path = shutil.which("tesseract")
    if on_path:
        pytesseract.pytesseract.tesseract_cmd = on_path
        return

    if Path(WINDOWS_TESSERACT).exists():
        pytesseract.pytesseract.tesseract_cmd = WINDOWS_TESSERACT
        return

    raise RuntimeError(
        "Tesseract OCR was not found. Install it (Windows: UB-Mannheim installer, "
        "Linux: sudo apt install tesseract-ocr tesseract-ocr-urd) or set the "
        "TESSERACT_CMD environment variable to the full path of tesseract.exe."
    )


def _pick_lang():
    """Use 'eng+urd' if Urdu data is installed, otherwise 'eng'."""
    global _lang_cache
    if _lang_cache is not None:
        return _lang_cache
    try:
        langs = pytesseract.get_languages(config="")
    except Exception:
        langs = []
    _lang_cache = "eng+urd" if "urd" in langs else "eng"
    return _lang_cache


def ocr_image(path):
    """Read text from an image file. Raises RuntimeError with a clear message on failure."""
    p = Path(path)
    if not p.is_file():
        raise RuntimeError("Image file not found: " + str(path))

    _configure_tesseract()

    try:
        with Image.open(p) as opened:
            opened.load()
            img = ImageOps.exif_transpose(opened)  # fix phone-photo rotation
            if img.mode in ("RGBA", "LA", "P"):
                # Put transparent images on a white background so text stays visible.
                rgba = img.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.split()[-1])
                img = background
            elif img.mode != "RGB" and img.mode != "L":
                img = img.convert("RGB")
            text = pytesseract.image_to_string(img, lang=_pick_lang())
    except RuntimeError:
        raise
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError("Tesseract executable could not be started: " + str(e)) from e
    except Exception as e:
        raise RuntimeError("OCR failed for " + p.name + ": " + str(e)) from e

    return text.strip()


# --------------------------------------------------------------------------
# Forgery heuristics (NOT proof)
# --------------------------------------------------------------------------
_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALES = {
    "thousand": 1000, "lakh": 100000, "lakhs": 100000, "lac": 100000,
    "lacs": 100000, "million": 1000000, "crore": 10000000,
    "crores": 10000000, "billion": 1000000000,
}


def _words_to_number(phrase):
    """'ten thousand' -> 10000. Returns None if any word is not understood."""
    tokens = [t for t in re.split(r"[\s\-,]+", phrase.lower().strip()) if t and t != "and"]
    if not tokens:
        return None
    total = 0
    current = 0
    for t in tokens:
        if t in _UNITS:
            current += _UNITS[t]
        elif t in _TENS:
            current += _TENS[t]
        elif t == "hundred":
            current = (current or 1) * 100
        elif t in _SCALES:
            total += (current or 1) * _SCALES[t]
            current = 0
        else:
            return None
    return total + current


def _digits_to_number(s):
    try:
        return float(s.replace(",", "").rstrip("."))
    except ValueError:
        return None


def _fmt_money(n):
    if float(n).is_integer():
        return "Rs " + format(int(n), ",")
    return "Rs " + str(n)


_DIGIT_AMOUNT_BEFORE = re.compile(
    r"\b(?:rs\.?|pkr|rupees)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE
)
_DIGIT_AMOUNT_AFTER = re.compile(
    r"\b([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:rs\b|pkr\b|rupees\b|/-)", re.IGNORECASE
)
_WORD_AMOUNT = re.compile(
    r"\b(?:rupees|rs\.?)\s+([a-z][a-z\s\-,]{0,120}?)\s+only\b", re.IGNORECASE
)


def _check_amount_mismatch(text):
    digit_values = set()
    for pattern in (_DIGIT_AMOUNT_BEFORE, _DIGIT_AMOUNT_AFTER):
        for m in pattern.finditer(text):
            v = _digits_to_number(m.group(1))
            if v is not None:
                digit_values.add(v)

    word_values = set()
    for m in _WORD_AMOUNT.finditer(text):
        v = _words_to_number(m.group(1))
        if v is not None:
            word_values.add(float(v))

    if digit_values and word_values and not (digit_values & word_values):
        digits_txt = ", ".join(_fmt_money(v) for v in sorted(digit_values))
        words_txt = ", ".join(_fmt_money(v) for v in sorted(word_values))
        return (
            "amount_mismatch: digits show " + digits_txt + " but the amount in words reads "
            + words_txt + " (heuristic, not proof)"
        )
    return None


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_RE = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"

_DATE_NUMERIC = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DATE_DAY_MONTH = re.compile(
    r"\b(\d{1,2})\s+(" + _MONTH_RE + r")[a-z]*\.?,?\s+(\d{4})\b", re.IGNORECASE
)
_DATE_MONTH_DAY = re.compile(
    r"\b(" + _MONTH_RE + r")[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b", re.IGNORECASE
)


def _safe_date(y, m, d):
    if y < 1900 or y > 2100:
        return None
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _find_dates(text):
    found = set()
    for m in _DATE_NUMERIC.finditer(text):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        d = _safe_date(y, b, a) or _safe_date(y, a, b)  # day-first, then month-first
        if d:
            found.add(d)
    for m in _DATE_ISO.finditer(text):
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            found.add(d)
    for m in _DATE_DAY_MONTH.finditer(text):
        d = _safe_date(int(m.group(3)), _MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
        if d:
            found.add(d)
    for m in _DATE_MONTH_DAY.finditer(text):
        d = _safe_date(int(m.group(3)), _MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
        if d:
            found.add(d)
    return found


_TEMPLATE_PHRASES = [
    "official seal", "official stamp", "government of pakistan",
    "ministry of", "official notification", "authorized signature",
    "authorised signature", "benazir income support", "bisp", "ehsaas",
    "nadra", "state bank of pakistan", "prime minister",
]
MIN_WORDS_FOR_TEMPLATE = 25   # fewer words than this next to a template phrase looks suspicious
MIN_WORDS_READABLE = 3        # fewer words than this = basically unreadable


def _word_count(text):
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def forgery_flags(text, image_path=None):
    """
    Return a list of human-readable flag strings. HEURISTICS ONLY, NOT PROOF.
    An empty list does not mean the document is genuine.
    """
    text = text or ""
    flags = []
    words = _word_count(text)

    # 1. Almost no readable text
    if words < MIN_WORDS_READABLE:
        flags.append(
            "unreadable_text: almost no readable text was found, so the document "
            "could not be checked properly (heuristic, not proof)"
        )

    # 2. Digits vs amount-in-words mismatch
    mismatch = _check_amount_mismatch(text)
    if mismatch:
        flags.append(mismatch)

    # 3. Dates in the future
    today = date.today()
    future = sorted(d for d in _find_dates(text) if d > today)
    if future:
        flags.append(
            "future_date: found date(s) later than today: "
            + ", ".join(d.isoformat() for d in future) + " (heuristic, not proof)"
        )

    # 4. Official-looking template phrases with very little text
    lower = text.lower()
    hits = [
        p for p in _TEMPLATE_PHRASES
        if re.search(r"\b" + re.escape(p) + r"\b", lower)
    ]
    if hits and words < MIN_WORDS_FOR_TEMPLATE:
        flags.append(
            "template_low_text: official-looking phrase(s) (" + ", ".join(hits)
            + ") with very little other text (heuristic, not proof)"
        )

    # 5. Weak informational note: no EXIF metadata
    if image_path:
        try:
            with Image.open(image_path) as im:
                has_exif = len(im.getexif()) > 0
            if not has_exif:
                flags.append(
                    "no_exif: the image has no EXIF metadata. This is only a weak "
                    "informational note, because screenshots and chat apps remove "
                    "EXIF all the time (heuristic, not proof)"
                )
        except Exception:
            pass  # unreadable image: the other checks already cover it

    return flags
