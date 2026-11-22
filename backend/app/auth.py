# backend/app/auth.py
"""Re-export security utilities for backward/cross-phase compatibility."""
from .security import (
    ALLOWED_SIGNUP_ROLES,
    ROLES,
    create_access_token,
    create_token,
    decode_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
