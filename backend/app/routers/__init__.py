# backend/app/routers/__init__.py
"""Routers package re-exporting all routers."""
from . import (
    audit_routes,
    auth_routes,
    cases,
    consent,
    decision_routes,
    mock_services,
)

all_routers = [
    auth_routes.router,
    cases.router,
    consent.router,
    decision_routes.router,
    audit_routes.router,
    mock_services.router,
]
