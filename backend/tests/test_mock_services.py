# backend/tests/test_mock_services.py
"""Mock services tests: schemes, NADRA, Raast, SMS + audit rows."""
import sqlite3
import time

ADMIN = {"name": "Admin Sahab", "phone": "03000000001", "password": "admin123", "role": "admin"}

VALID_EVEN_CNIC = "42101-1234567-2"  # last digit even -> verified True
VALID_ODD_CNIC = "42101-1234567-3"   # last digit odd  -> verified False


def _setup_admin(client):
    resp = client.post("/api/auth/register", json=ADMIN)
    assert resp.status_code == 201
    resp = client.post("/api/auth/login", json={"phone": ADMIN["phone"], "password": ADMIN["password"]})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _audit_rows():
    from app.database import DATABASE_URL

    con = sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""))
    rows = list(con.execute("SELECT actor_id, action FROM audit_log ORDER BY id"))
    con.close()
    return rows


# ---------- schemes (public, no login) ----------

def test_schemes_public_no_auth_returns_5(client):
    resp = client.get("/api/mock/schemes")
    assert resp.status_code == 200
    schemes = resp.json()
    assert isinstance(schemes, list)
    assert len(schemes) == 5
    for s in schemes:
        assert s["name"]
        assert s["eligibility"]
        assert s["never_asks_money"] is True


# ---------- all POST endpoints require login ----------

def test_nadra_requires_login_401(client):
    resp = client.post("/api/mock/nadra", json={"cnic": VALID_EVEN_CNIC})
    assert resp.status_code == 401


def test_raast_requires_login_401(client):
    resp = client.post(
        "/api/mock/raast",
        json={"from_cnic": VALID_EVEN_CNIC, "to_cnic": VALID_ODD_CNIC, "amount": 100},
    )
    assert resp.status_code == 401


def test_sms_send_requires_login_401(client):
    resp = client.post("/api/mock/sms/send", json={"phone": "03001234567", "body": "hi"})
    assert resp.status_code == 401


# ---------- NADRA ----------

def test_nadra_even_last_digit_verified_true(client):
    headers = _setup_admin(client)
    resp = client.post("/api/mock/nadra", json={"cnic": VALID_EVEN_CNIC}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True
    assert body["name"]  # a fake name is always returned
    assert "MOCK" in body["source"].upper()


def test_nadra_odd_last_digit_verified_false(client):
    headers = _setup_admin(client)
    resp = client.post("/api/mock/nadra", json={"cnic": VALID_ODD_CNIC}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["verified"] is False


def test_nadra_same_cnic_same_fake_name(client):
    headers = _setup_admin(client)
    r1 = client.post("/api/mock/nadra", json={"cnic": VALID_EVEN_CNIC}, headers=headers).json()
    r2 = client.post("/api/mock/nadra", json={"cnic": VALID_EVEN_CNIC}, headers=headers).json()
    assert r1["name"] == r2["name"]  # deterministic fake name per CNIC


def test_nadra_bad_format_422(client):
    headers = _setup_admin(client)
    for bad in ["421011234567", "42101-12345678-1", "abcde-1234567-1", "42101-1234567-x", ""]:
        resp = client.post("/api/mock/nadra", json={"cnic": bad}, headers=headers)
        assert resp.status_code == 422, bad


def test_nadra_delay_at_least_1_5s(client):
    headers = _setup_admin(client)
    start = time.monotonic()
    resp = client.post("/api/mock/nadra", json={"cnic": VALID_EVEN_CNIC}, headers=headers)
    elapsed = time.monotonic() - start
    assert resp.status_code == 200
    assert elapsed >= 1.4  # the 1.5s simulated processing delay


def test_nadra_writes_audit_row(client):
    headers = _setup_admin(client)
    resp = client.post("/api/mock/nadra", json={"cnic": VALID_EVEN_CNIC}, headers=headers)
    assert resp.status_code == 200
    actions = [r[1] for r in _audit_rows()]
    assert "mock.nadra_verify" in actions


# ---------- Raast ----------

def test_raast_returns_pending_mock_txn(client):
    headers = _setup_admin(client)
    resp = client.post(
        "/api/mock/raast",
        json={"from_cnic": VALID_EVEN_CNIC, "to_cnic": VALID_ODD_CNIC, "amount": 25000},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["txn_id"].startswith("MOCK-")
    assert body["status"] == "pending"
    assert body["note"] == "simulated"
    actions = [r[1] for r in _audit_rows()]
    assert "mock.raast_transfer" in actions


def test_raast_bad_cnic_or_amount_422(client):
    headers = _setup_admin(client)
    bad1 = client.post(
        "/api/mock/raast",
        json={"from_cnic": "12345", "to_cnic": VALID_ODD_CNIC, "amount": 100},
        headers=headers,
    )
    assert bad1.status_code == 422
    bad2 = client.post(
        "/api/mock/raast",
        json={"from_cnic": VALID_EVEN_CNIC, "to_cnic": VALID_ODD_CNIC, "amount": 0},
        headers=headers,
    )
    assert bad2.status_code == 422
    bad3 = client.post(
        "/api/mock/raast",
        json={"from_cnic": VALID_EVEN_CNIC, "to_cnic": VALID_ODD_CNIC, "amount": -5},
        headers=headers,
    )
    assert bad3.status_code == 422


# ---------- SMS ----------

def test_sms_send_stores_notification_and_audits(client):
    headers = _setup_admin(client)
    resp = client.post(
        "/api/mock/sms/send",
        json={"phone": "03001234567", "body": "Aap ka case update: qist approve ho gayi hai."},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is True
    assert isinstance(body["notification_id"], int)

    from app.database import DATABASE_URL

    con = sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""))
    row = con.execute("SELECT user_id, channel, body FROM notifications ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    assert row is not None
    assert row[1] == "sms"
    assert row[2].startswith("Aap ka case update")
    actions = [r[1] for r in _audit_rows()]
    assert "mock.sms_send" in actions


def test_sms_to_registered_user_links_notification(client):
    headers = _setup_admin(client)
    resp = client.post(
        "/api/mock/sms/send",
        json={"phone": ADMIN["phone"], "body": "hello admin"},
        headers=headers,
    )
    assert resp.status_code == 200

    from app.database import DATABASE_URL

    con = sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""))
    row = con.execute("SELECT user_id FROM notifications ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    assert row[0] == 1  # linked to the admin user (first user in a fresh DB)


def test_sms_bad_phone_422(client):
    headers = _setup_admin(client)
    resp = client.post("/api/mock/sms/send", json={"phone": "not-a-phone", "body": "hi"}, headers=headers)
    assert resp.status_code == 422


# ---------- audit coverage for all three POSTs ----------

def test_all_three_mock_posts_are_audited_with_actor(client):
    headers = _setup_admin(client)
    assert client.post("/api/mock/nadra", json={"cnic": VALID_EVEN_CNIC}, headers=headers).status_code == 200
    assert (
        client.post(
            "/api/mock/raast",
            json={"from_cnic": VALID_EVEN_CNIC, "to_cnic": VALID_ODD_CNIC, "amount": 500},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post("/api/mock/sms/send", json={"phone": "03001234567", "body": "x"}, headers=headers).status_code
        == 200
    )

    rows = _audit_rows()
    actions = {r[1] for r in rows}
    assert {"mock.nadra_verify", "mock.raast_transfer", "mock.sms_send"} <= actions
    actors = {r[0] for r in rows if r[1].startswith("mock.")}
    assert actors == {1}  # every mock action carries the acting admin's id
