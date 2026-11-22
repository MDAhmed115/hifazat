# backend/tests/test_audit_routes.py
"""Tests for the auditor read-only endpoints.

Covers:
  - GET /api/audit            (auditor only, pagination + filters + newest-first)
  - GET /api/decisions/{id}/trace (auditor + officer, full trace JSON)
  - GET /api/consent/records  (auditor only)
  - RBAC: citizen/officer/admin blocked where they must be; 401 without token
  - READ-ONLY: POST/PATCH to audit endpoints -> 405; auditor POST/PATCH on
    other routers' write endpoints -> 403 via require_role
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Decision  # noqa: E402

client = TestClient(app)
PW = "Passw0rd!"


def login(email: str) -> str:
    r = client.post("/api/auth/login", data={"username": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def seed_once():
    import seed as seed_mod
    seed_mod.seed()


def test_health_labels_prototype():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["environment"] == "PROTOTYPE"
    assert "mock" in body["notice"].lower()


def test_audit_requires_auth():
    r = client.get("/api/audit")
    assert r.status_code == 401


def test_audit_denied_for_non_auditors():
    for email in ["ayesha@example.com", "bilal@example.com", "imran@example.com", "admin@example.com"]:
        r = client.get("/api/audit", headers=auth(login(email)))
        assert r.status_code == 403, f"{email} should be 403, got {r.status_code}"


def test_audit_paginated_newest_first_and_filters():
    t = login("auditor@example.com")
    r = client.get("/api/audit", headers=auth(t))
    assert r.status_code == 200
    page = r.json()
    assert page["page"] == 1 and page["page_size"] == 20
    assert page["total"] >= len(page["items"]) > 0
    created = [row["created_at"] for row in page["items"]]
    assert created == sorted(created, reverse=True), "must be ordered newest first"

    # action filter
    r = client.get("/api/audit", params={"action": "case_created"}, headers=auth(t))
    assert r.status_code == 200
    for row in r.json()["items"]:
        assert row["action"] == "case_created"

    # entity_type filter
    r = client.get("/api/audit", params={"entity_type": "decision"}, headers=auth(t))
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    for row in r.json()["items"]:
        assert row["entity_type"] == "decision"

    # date window: everything is created today, so today's window must cover all
    today = dt.date.today().isoformat()
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    r = client.get("/api/audit", params={"date_from": today, "date_to": today}, headers=auth(t))
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    r = client.get("/api/audit", params={"date_from": yesterday, "date_to": yesterday}, headers=auth(t))
    assert r.json()["total"] == 0, "no rows should exist before seeding"

    # invalid date -> 422
    r = client.get("/api/audit", params={"date_from": "not-a-date"}, headers=auth(t))
    assert r.status_code == 422

    # pagination walk
    r1 = client.get("/api/audit", params={"page": 1, "page_size": 3}, headers=auth(t))
    r2 = client.get("/api/audit", params={"page": 2, "page_size": 3}, headers=auth(t))
    ids1 = {row["id"] for row in r1.json()["items"]}
    ids2 = {row["id"] for row in r2.json()["items"]}
    assert not (ids1 & ids2), "pages must not overlap"
    assert len(r1.json()["items"]) == 3


def test_decision_trace_full_json():
    t = login("auditor@example.com")
    db = SessionLocal()
    dec = db.query(Decision).order_by(Decision.id.desc()).first()
    db.close()
    assert dec is not None

    r = client.get(f"/api/decisions/{dec.id}/trace", headers=auth(t))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == dec.id
    # FULL explanation_audit JSON present with the keys the auditor needs
    for key in ["engine", "label", "confidence", "thresholds_applied", "high_risk_keywords"]:
        assert key in body["explanation_audit"], f"missing {key} in explanation_audit"
    assert "rag_matches" in body["sources"]
    assert body["rule_version"] is not None
    assert body["rule_version"]["version"] == "v1.0"
    assert body["rule_version"]["thresholds"] == {"auto": 0.85, "ask": 0.60}
    assert body["label"] in ["scam", "genuine", "complaint", "service_request"]
    assert 0.0 <= body["confidence"] <= 1.0

    # officer can read it too
    r = client.get(f"/api/decisions/{dec.id}/trace", headers=auth(login("imran@example.com")))
    assert r.status_code == 200

    # 404 on unknown decision
    r = client.get("/api/decisions/999999/trace", headers=auth(t))
    assert r.status_code == 404


def test_decision_trace_denied_for_citizen_helper_admin():
    dec_id = _any_decision_id()
    for email in ["ayesha@example.com", "bilal@example.com", "admin@example.com"]:
        r = client.get(f"/api/decisions/{dec_id}/trace", headers=auth(login(email)))
        assert r.status_code == 403, f"{email} should be 403, got {r.status_code}"


def _any_decision_id() -> int:
    db = SessionLocal()
    dec = db.query(Decision).order_by(Decision.id.desc()).first()
    db.close()
    return dec.id


def test_consent_records_auditor_only():
    t = login("auditor@example.com")
    r = client.get("/api/consent/records", headers=auth(t))
    assert r.status_code == 200
    records = r.json()
    assert len(records) >= 3
    assert {rec["consent_type"] for rec in records} >= {"data_processing", "ai_analysis"}
    assert all(rec["granted"] is True for rec in records)

    for email in ["ayesha@example.com", "imran@example.com", "admin@example.com"]:
        r = client.get("/api/consent/records", headers=auth(login(email)))
        assert r.status_code == 403, f"{email} should be 403, got {r.status_code}"

    r = client.get("/api/consent/records")
    assert r.status_code == 401


def test_audit_endpoints_are_read_only():
    """POST/PATCH to the audit endpoints must not create anything: 405."""
    t = login("auditor@example.com")
    for method, path in [
        ("post", "/api/audit"),
        ("patch", "/api/audit"),
        ("post", "/api/consent/records"),
        ("patch", "/api/consent/records"),
        ("post", "/api/decisions/1/trace"),
    ]:
        r = getattr(client, method)(path, headers=auth(t), json={"x": 1})
        assert r.status_code == 405, f"{method.upper()} {path} should be 405, got {r.status_code}"


def test_auditor_cannot_mutate_other_routes():
    """require_role blocks auditor from every write endpoint elsewhere."""
    t = login("auditor@example.com")
    # submit case (citizen-only write)
    r = client.post("/api/cases", headers=auth(t), json={"channel": "sms", "content": "hello auditor write attempt"})
    assert r.status_code == 403, r.text
    # officer-only status change
    r = client.patch("/api/cases/1/status", headers=auth(t), params={"new_status": "resolved"})
    assert r.status_code == 403, r.text
    # consent write (citizen-only)
    r = client.post("/api/consent", headers=auth(t), json={"consent_type": "contact", "granted": True})
    assert r.status_code == 403, r.text


def test_mutation_writes_audit_log():
    """Every mutation writes an audit_log row via log_action()."""
    t = login("auditor@example.com")
    before = client.get("/api/audit", params={"page_size": 100}, headers=auth(t)).json()["total"]
    c = login("ayesha@example.com")
    r = client.post("/api/cases", headers=auth(c), json={"channel": "sms", "content": "Test SMS for audit logging"})
    assert r.status_code == 201
    after = client.get("/api/audit", params={"page_size": 100}, headers=auth(t)).json()["total"]
    assert after == before + 2  # ayesha login + case_created (auditor token reused)
