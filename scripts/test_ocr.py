# scripts/test_ocr.py
"""
Tests for app/ai/ocr.py.
Generates its own PNG with Pillow (nothing to download), runs OCR,
and checks every forgery heuristic. Heuristics are NOT proof.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.ai.ocr import FORGERY_NOTE, forgery_flags, ocr_image  # noqa: E402


def has_flag(flags, prefix):
    return any(f.startswith(prefix) for f in flags)


def make_png(path):
    im = Image.new("RGB", (1000, 200), "white")
    d = ImageDraw.Draw(im)
    d.text(
        (30, 60),
        "Hifazat Relief Rs 5000",
        font=ImageFont.load_default(size=56),
        fill="black",
    )
    im.save(path)


def t1_ocr_reads_text():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.png"
        make_png(p)
        text = ocr_image(p)
    norm = text.lower().replace(",", "").replace(" ", "")
    ok = "hifazat" in norm and "5000" in norm
    return ok, "OCR text: " + repr(text)


def t2_amount_mismatch():
    bad = forgery_flags("Rs 5,000 Rupees Ten Thousand Only")
    good = forgery_flags("Rs 5,000 Rupees Five Thousand Only")
    ok = has_flag(bad, "amount_mismatch") and not has_flag(good, "amount_mismatch")
    return ok, "mismatch flagged: " + str(has_flag(bad, "amount_mismatch")) + ", matching amounts flagged: " + str(has_flag(good, "amount_mismatch"))


def t3_future_date():
    future = forgery_flags("Payment date: 15/03/2099 reference 12345")
    past = forgery_flags("Payment date: 01/01/2020 reference 12345")
    ok = has_flag(future, "future_date") and not has_flag(past, "future_date")
    return ok, "2099 flagged: " + str(has_flag(future, "future_date")) + ", 2020 flagged: " + str(has_flag(past, "future_date"))


def t4_template_low_text():
    short = forgery_flags("OFFICIAL SEAL Government of Pakistan Relief Payment")
    long_text = "OFFICIAL SEAL " + " ".join(["details"] * 40)
    long_flags = forgery_flags(long_text)
    ok = has_flag(short, "template_low_text") and not has_flag(long_flags, "template_low_text")
    return ok, "short flagged: " + str(has_flag(short, "template_low_text")) + ", long flagged: " + str(has_flag(long_flags, "template_low_text"))


def t5_unreadable_exif_and_honesty():
    empty = forgery_flags("")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.png"
        make_png(p)
        with_image = forgery_flags("Hello this is some readable text", image_path=p)
    all_flags = empty + with_image
    honest = all(("heuristic, not proof" in f) for f in all_flags)
    ok = has_flag(empty, "unreadable_text") and has_flag(with_image, "no_exif") and honest and len(all_flags) > 0
    return ok, "unreadable: " + str(has_flag(empty, "unreadable_text")) + ", no_exif: " + str(has_flag(with_image, "no_exif")) + ", all flags say heuristic: " + str(honest)


TESTS = [
    ("OCR reads text from a generated PNG", t1_ocr_reads_text),
    ("Digits vs amount-in-words mismatch", t2_amount_mismatch),
    ("Future dates are flagged", t3_future_date),
    ("Template phrase with very little text", t4_template_low_text),
    ("Unreadable text + EXIF note + honest wording", t5_unreadable_exif_and_honesty),
]


def main():
    passed = 0
    for i, (name, fn) in enumerate(TESTS, start=1):
        try:
            ok, detail = fn()
        except Exception as e:  # a crash is a FAIL, not a traceback
            ok, detail = False, "crashed: " + type(e).__name__ + ": " + str(e)
        print(("PASS" if ok else "FAIL") + " " + str(i) + ". " + name)
        print("       " + detail)
        if ok:
            passed += 1
    print()
    print("Score: " + str(passed) + "/" + str(len(TESTS)) + " passed")
    print("Reminder: " + FORGERY_NOTE)
    sys.exit(0 if passed == len(TESTS) else 1)


if __name__ == "__main__":
    main()
