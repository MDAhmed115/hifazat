# backend/tests/test_auth.py
"""Auth API tests: registration, bootstrap admin, login, RBAC, audit trail."""
import sqlite3

import pytest

ADMIN = {"name": "Admin Sahab", "phone": "03000000001", "password": "admin123", "role": "admin"}
CITIZEN = {"name": "Ali Raza", "phone": "03000000002", "password": "citizen123", "role": "citizen"}
OFFICER = {"name": "Officer Khan", "phone": "03000000003", "password": "officer123", "role": "officer"}


def _register(client, payload):
    return client.post("/api/auth/register", json=payload)


def _login(client, phone, password):
    return client.post("/api/auth/login", json={"phone": phone, "password": password})


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- health ----------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ---------- registration ----------

def test_first_user_can_be_admin(client):
    resp = _register(client, ADMIN)
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "admin"
    assert body["is_active"] is True
    assert "id" in body and "hashed_password" not in body


def test_second_admin_rejected_403(client):
    _register(client, ADMIN)
    second = dict(ADMIN, phone="03000000009", name="Sneaky Admin")
    resp = _register(client, second)
    assert resp.status_code == 403
    assert "bootstrap admin already exists" in resp.json()["detail"]


def test_citizen_and_officer_register_201(client):
    assert _register(client, CITIZEN).status_code == 201
    assert _register(client, OFFICER).status_code == 201


def test_duplicate_phone_conflict_409(client):
    _register(client, CITIZEN)
    dup = dict(CITIZEN, name="Duplicate")
    resp = _register(client, dup)
    assert resp.status_code == 409


def test_invalid_role_rejected_422(client):
    bad = {"name": "X", "phone": "03000000005", "password": "abc123", "role": "superuser"}
    resp = _register(client, bad)
    assert resp.status_code == 422


def test_short_password_rejected_422(client):
    bad = {"name": "X", "phone": "03000000006", "password": "abc", "role": "citizen"}
    resp = _register(client, bad)
    assert resp.status_code == 422


# ---------- login ----------

def test_login_returns_token_role_name(client):
    _register(client, CITIZEN)
    resp = _login(client, CITIZEN["phone"], CITIZEN["password"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "citizen"
    assert body["name"] == "Ali Raza"
    assert body["token"].count(".") == 2  # JWT has 3 parts


def test_login_wrong_password_401(client):
    _register(client, CITIZEN)
    resp = _login(client, CITIZEN["phone"], "wrongpass")
    assert resp.status_code == 401


def test_login_unknown_phone_401(client):
    resp = _login(client, "03000099999", "whatever")
    assert resp.status_code == 401


def test_jwt_expires_in_12_hours(client):
    import base64
    import json as jsonlib
    _register(client, CITIZEN)
    token = _login(client, CITIZEN["phone"], CITIZEN["password"]).json()["token"]
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)  # base64url padding
    payload = jsonlib.loads(base64.urlsafe_b64decode(payload_b64))
    assert payload["exp"] - payload["iat"] == 12 * 3600
    assert payload["role"] == "citizen"
    assert payload["name"] == "Ali Raza"


# ---------- /me ----------

def test_me_returns_profile(client):
    _register(client, CITIZEN)
    token = _login(client, CITIZEN["phone"], CITIZEN["password"]).json()["token"]
    resp = client.get("/api/auth/me", headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["phone"] == CITIZEN["phone"]
    assert body["role"] == "citizen"
    assert "hashed_password" not in body


def test_me_without_token_401(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_garbage_token_401(client):
    resp = client.get("/api/auth/me", headers=_auth_header("abc.def.ghi"))
    assert resp.status_code == 401


# ---------- RBAC ----------

def test_officer_endpoint_allows_officer(client):
    _register(client, OFFICER)
    token = _login(client, OFFICER["phone"], OFFICER["password"]).json()["token"]
    resp = client.get("/api/auth/officer-only", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_officer_endpoint_forbids_citizen_403(client):
    _register(client, CITIZEN)
    token = _login(client, CITIZEN["phone"], CITIZEN["password"]).json()["token"]
    resp = client.get("/api/auth/officer-only", headers=_auth_header(token))
    assert resp.status_code == 403
    assert "not allowed" in resp.json()["detail"]


def test_admin_also_forbidden_on_officer_only(client):
    """require_role('officer') must not silently admit admins: strict RBAC."""
    _register(client, ADMIN)
    token = _login(client, ADMIN["phone"], ADMIN["password"]).json()["token"]
    resp = client.get("/api/auth/officer-only", headers=_auth_header(token))
    assert resp.status_code == 403


# ---------- audit trail ----------

def test_audit_rows_written_for_register_and_login(client):
    _register(client, CITIZEN)
    _login(client, CITIZEN["phone"], CITIZEN["password"])
    _login(client, CITIZEN["phone"], "wrongpass")  # failed login is audited too

    from app.database import DATABASE_URL
    db_path = DATABASE_URL.replace("sqlite:///", "")
    con = sqlite3.connect(db_path)
    rows = list(con.execute("SELECT actor_id, action FROM audit_log ORDER BY id"))
    con.close()

    actions = [r[1] for r in rows]
    assert "user.register" in actions
    assert "user.login" in actions
    assert "user.login_failed" in actions
    # register and successful login carry the actor id (citizen id = 1 here)
    actor_ids = {r[0] for r in rows if r[1] in ("user.register", "user.login")}
    assert actor_ids == {1}
