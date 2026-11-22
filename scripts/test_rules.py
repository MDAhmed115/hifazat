# scripts/test_rules.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.ai import engine, guardrails
from app.rules_engine import default_rules

rules = default_rules()
results = []


def check(name, ok, note=""):
    results.append(bool(ok))
    print("PASS" if ok else "FAIL", "|", name, ("| " + note if note else ""))


r = guardrails.pre_check("Please send your OTP now", rules)
check("OTP -> human", r and r["route"] == "human" and "otp" in r["matched"], str(r))
check("'shipping' does not match 'pin'", guardrails.pre_check("Your shipping update is ready", rules) is None)
check("Urdu keyword", guardrails.pre_check("آپ کا انعام نکلا ہے", rules) is not None)
check("Roman Urdu keyword", guardrails.pre_check("Aap jeet gaye hain", rules) is not None)


def route(label, conf, rl=rules):
    return guardrails.route_decision(label, conf, rl)["route"]


check("scam 0.90 -> auto", route("scam", 0.90) == "auto")
check("scam 0.70 -> ask_more", route("scam", 0.70) == "ask_more")
check("genuine 0.88 -> ask_more (stricter than scam)", route("genuine", 0.88) == "ask_more")
check("genuine 0.93 -> auto", route("genuine", 0.93) == "auto")
check("confidence 0.40 -> human", route("scam", 0.40) == "human")
check("uncertain -> human", route("uncertain", 0.99) == "human")

rules_v2 = dict(rules, auto_scam_threshold=0.95)
check("same scam 0.90: v1 auto, v2 ask_more", route("scam", 0.90, rules) == "auto" and route("scam", 0.90, rules_v2) == "ask_more")


def boom(_):
    raise AssertionError("AI was called for an OTP message!")


engine.classify = boom
out = engine.decide_core("Send OTP and PIN to 0300-1234567", rules, 1)
check("OTP message: human, AI not called", out["route"] == "human" and out["explanation_audit"]["ai_called"] is False,
      "matched=" + str(out["matched_keywords"]))
check("audit trace has rule_version_no", out["explanation_audit"]["rule_version_no"] == 1)

print("\n%d/%d passed" % (sum(results), len(results)))
