# backend/app/routers/consent_routes.py
"""Alias router file pointing to consent.py."""
from .consent import (
    SHARABLE_ROLES,
    check_consent,
    log_data_access,
    router,
)
