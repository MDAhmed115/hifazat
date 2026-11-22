# backend/tests/test_seed.py
"""Seed script tests: exact row counts, messy duplicate names, idempotency."""
import sqlite3

import pytest


def _db_path():
    from app.database import DATABASE_URL

    return DATABASE_URL.replace("sqlite:///", "")


def _counts():
    con = sqlite3.connect(_db_path())
    counts = {}
    for table in ["users", "citizens", "cases", "messages", "decisions", "rule_versions", "audit_log"]:
        counts[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    con.close()
    return counts


@pytest.fixture()
def fresh_db():
    """Drop and recreate all tables so the seed starts from an empty database."""
    from app.database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_seed_creates_exact_rows(fresh_db):
    from scripts.seed import run_seed

    result = run_seed()
    assert result["created"] is True

    c = _counts()
    assert c["users"] == 5  # 1 admin + 2 officers + 1 helper + 1 citizen login
    assert c["citizens"] == 3
    assert c["cases"] == 5
    assert c["messages"] == 10
    assert c["decisions"] == 5
    assert c["rule_versions"] == 5
    assert c["audit_log"] == 20


def test_seed_messy_duplicate_names_share_one_user(fresh_db):
    from scripts.seed import run_seed

    run_seed()
    con = sqlite3.connect(_db_path())
    rows = list(con.execute("SELECT full_name, user_id, cnic FROM citizens ORDER BY id"))
    con.close()

    names = [r[0] for r in rows]
    assert names == ["Muhammad Ashraf", "Mohammad Ashraf", "M. Ashraf"]
    # all three link to the SAME user account -> the same phone number
    assert len({r[1] for r in rows}) == 1
    # but each profile has a distinct CNIC (cnic is unique)
    assert len({r[2] for r in rows}) == 3


def test_seed_is_idempotent(fresh_db):
    from scripts.seed import run_seed

    run_seed()
    before = _counts()

    second = run_seed()  # admin exists now -> must skip, not duplicate
    assert second["created"] is False
    assert _counts() == before


def test_seed_only_last_rule_version_active(fresh_db):
    from scripts.seed import run_seed

    run_seed()
    con = sqlite3.connect(_db_path())
    rows = list(con.execute("SELECT version, active FROM rule_versions ORDER BY id"))
    con.close()

    assert len(rows) == 5
    assert [r[0] for r in rows] == ["v0.1", "v0.2", "v0.3", "v0.4", "v1.4"]
    assert [r[1] for r in rows] == [0, 0, 0, 0, 1]  # only v1.4 is active


def test_seed_decisions_have_urdu_explanations_and_routes(fresh_db):
    from scripts.seed import run_seed

    run_seed()
    con = sqlite3.connect(_db_path())
    rows = list(con.execute("SELECT route, confidence, explanation_ur, trace_json FROM decisions"))
    con.close()

    assert len(rows) == 5
    routes = {r[0] for r in rows}
    assert routes <= {"auto_handle", "ask_more_proof", "human_handoff"}
    assert "ask_more_proof" in routes and "human_handoff" in routes
    for r in rows:
        assert r[1] >= 0.60
        assert len(r[2]) > 10  # Urdu explanation present
        assert "seed_offline_rules" in r[3]  # trace stored


def test_seeded_admin_can_login(client):
    from scripts.seed import run_seed

    run_seed()  # the client fixture already reset the tables
    resp = client.post("/api/auth/login", json={"phone": "03000000000", "password": "admin123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin"
    assert body["name"] == "Hifazat Admin"
    assert body["token"].count(".") == 2
