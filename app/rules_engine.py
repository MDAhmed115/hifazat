# backend/app/rules_engine.py
"""Loads / changes the routing rules. Rules live in the rule_versions table.
Every change creates a NEW row (version_no + 1); old rows get active=False, so an
old decision still points to the version that was in force when it was made."""
import copy
from datetime import datetime, timezone

DEFAULT_RULES = {
    "auto_scam_threshold": 0.85,
    "auto_genuine_threshold": 0.90,
    "human_threshold": 0.60,
    "high_risk_keywords": [
        "otp", "pin", "send money", "raast", "bank charges", "prize",
        "jeet gaye", "click link", "whatsapp number share",
        # extra Roman Urdu + Urdu script terms
        "paisay bhejein", "paise bhejein", "processing fee", "lucky draw",
        "او ٹی پی", "پن کوڈ", "انعام", "رقم بھیجیں", "پیسے بھیجیں", "لنک پر کلک",
    ],
    "schemes": ["BISP", "Ehsaas", "Bait-ul-Maal", "Zakat", "Benazir Kafaalat"],
}

NUMERIC_KEYS = ["auto_scam_threshold", "auto_genuine_threshold", "human_threshold"]


def default_rules():
    return copy.deepcopy(DEFAULT_RULES)


def _validate(rules):
    """Raise ValueError if the rules are not sane."""
    for k in NUMERIC_KEYS:
        v = rules.get(k)
        if not isinstance(v, (int, float)) or not (0.0 <= float(v) <= 1.0):
            raise ValueError(k + " must be a number between 0 and 1")
    if rules["human_threshold"] >= min(rules["auto_scam_threshold"], rules["auto_genuine_threshold"]):
        raise ValueError("human_threshold must be lower than both auto thresholds")
    kw = rules.get("high_risk_keywords")
    if not isinstance(kw, list) or not all(isinstance(x, str) for x in kw):
        raise ValueError("high_risk_keywords must be a list of strings")
    if not isinstance(rules.get("schemes"), list):
        raise ValueError("schemes must be a list")


# ---- DB layer (adapted to the team's rule_versions table) ----
import re


def _models():
    # lazy import so this file can be tested without the database code
    from app.models import RuleVersion
    return RuleVersion


# The team's seeded rules (scripts/seed.py) use other key names than this engine.
# ASSUMPTION: map their names onto ours so their thresholds are really used.
TEAM_KEY_MAP = {
    "auto_handle_min_confidence": "auto_scam_threshold",
    "ask_more_proof_min_confidence": "human_threshold",
    "human_handoff_max_confidence": "human_threshold",
}


def _translate_stored_rules(stored):
    """Merge a stored rules_json over the defaults.
    - team key names are translated to ours
    - high_risk_keywords are ADDED to the default list (union), so the Urdu and
      Roman Urdu keywords are never lost when a stored version lists fewer keywords
    - if the result is not valid, the safe defaults are used"""
    stored = dict(stored or {})
    translated = {}
    for key, value in stored.items():
        translated[TEAM_KEY_MAP.get(key, key)] = value
    if "human_handoff_max_confidence" in stored:
        translated["human_threshold"] = stored["human_handoff_max_confidence"]

    rules = default_rules()
    keywords = translated.pop("high_risk_keywords", None)
    rules.update(translated)
    if isinstance(keywords, list):
        merged = list(rules["high_risk_keywords"])
        for word in keywords:
            if isinstance(word, str) and word not in merged:
                merged.append(word)
        rules["high_risk_keywords"] = merged
    try:
        _validate(rules)
    except (ValueError, TypeError, KeyError):
        return default_rules()
    return rules


def get_active_rules(db):
    """Return (rules_dict, rule_version_id, rule_version_label).
    With db=None (tests) returns the defaults and (None, 0).
    If the table has no active row yet, creates version v1.0 from the defaults."""
    if db is None:
        return default_rules(), None, 0
    RuleVersion = _models()
    row = (db.query(RuleVersion).filter(RuleVersion.active == True)  # noqa: E712
           .order_by(RuleVersion.id.desc()).first())
    if row is None:
        row = RuleVersion(version="v1.0", rules_json=default_rules(), active=True)
        db.add(row)
        db.commit()
        db.refresh(row)
    return _translate_stored_rules(row.rules_json), row.id, row.version


def get_rules(db):
    """Return just the rules dict."""
    return get_active_rules(db)[0]


def _next_label(current_label, count):
    m = re.match(r"^v(\d+)\.(\d+)$", str(current_label))
    if m:
        return "v%d.%d" % (int(m.group(1)), int(m.group(2)) + 1)
    return "v%d.0" % (count + 1)


def apply_rule_change(db, rules_json, changed_by):
    """Merge rules_json over the current rules, validate, save as a new version.
    Old rows are set active=False. Returns the new row.
    NOTE: the team's table has no created_by column, so the caller should record
    who changed the rules with log_action()."""
    RuleVersion = _models()
    current, _, current_label = get_active_rules(db)
    new_rules = copy.deepcopy(current)
    new_rules.update(rules_json or {})
    _validate(new_rules)

    count = db.query(RuleVersion).count()
    db.query(RuleVersion).filter(RuleVersion.active == True).update({"active": False})  # noqa: E712
    row = RuleVersion(version=_next_label(current_label, count), rules_json=new_rules, active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
