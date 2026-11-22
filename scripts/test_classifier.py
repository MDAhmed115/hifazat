# scripts/test_classifier.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.ai.classifier import classify

CASES = [
    ("fake prize SMS -> scam, confidence > 0.85",
     "Congratulations! Aap ne Bait-ul-Maal Relief jeeta hai. Rs 250,000 prize claim karne ke liye Rs 250 processing fee Raast karein: 0300-7788990",
     lambda d: d["label"] == "scam" and d["confidence"] > 0.85),
    ("genuine message -> genuine",
     "BISP: Your installment is approved. Collect it from your nearest Ehsaas retailer with your CNIC. No fee is required.",
     lambda d: d["label"] == "genuine"),
    ("garbled text -> low confidence, no crash",
     "asdkj ### qwe 99 ?? lkj",
     lambda d: d["confidence"] < 0.7),
    ("OTP scam -> scam",
     "Aap ka relief account block ho jayega. Abhi apna OTP aur PIN bhejein 0300-1234567",
     lambda d: d["label"] == "scam"),
    ("complaint",
     "Mujhe 3 mahine se payment nahi mili, meri madad karein",
     lambda d: d["label"] == "complaint"),
    ("service request",
     "Relief scheme ke liye apply kaise karun? Kya shara'it hain?",
     lambda d: d["label"] == "service_request"),
]

passed = 0
for name, text, check in CASES:
    d = classify(text)
    ok = bool(check(d))
    passed += ok
    print("PASS" if ok else "FAIL", "|", name)
    print("     label=%s confidence=%s" % (d["label"], d["confidence"]))
    print("     reason:", d["reason_en"])

print("\n%d/%d passed" % (passed, len(CASES)))  