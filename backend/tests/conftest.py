# backend/tests/conftest.py
"""Pytest fixture: seed the database ONCE before the audit test session."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    import seed as seed_mod
    seed_mod.seed()
    yield
