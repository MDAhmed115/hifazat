# scripts/test_rag.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.ai.rag import rag_query

results = []


def check(name, ok):
    results.append(bool(ok))
    print("PASS" if ok else "FAIL", "|", name)


r = rag_query("Does Bait-ul-Maal ask for bank charges?")
print("  answer_en:", r["answer_en"])
print("  sources  :", [s["doc"] for s in r["sources"]])
check("bank charges -> answered with a source", r["answered"] and len(r["sources"]) > 0)
check("bank charges -> answer says no / never", any(w in r["answer_en"].lower() for w in ("no", "never", "not")))

r = rag_query("What is the income limit for Bait-ul-Maal relief?")
print("  answer_en:", r["answer_en"])
check("income limit -> mentions 40,000", "40,000" in r["answer_en"] and len(r["sources"]) > 0)

r = rag_query("How do I report a scam SMS?")
print("  answer_en:", r["answer_en"])
check("report scam SMS -> answered with a source", r["answered"] and len(r["sources"]) > 0)

r = rag_query("What is the weather on Mars?")
print("  answer_en:", r["answer_en"])
check("Mars -> refusal, empty sources", (not r["answered"]) and r["sources"] == [] and "don't have" in r["answer_en"])

r = rag_query("")
check("empty question -> refusal, no crash", not r["answered"])

print("\n%d/%d passed" % (sum(results), len(results)))
