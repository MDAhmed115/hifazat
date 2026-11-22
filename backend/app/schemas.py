# backend/app/schemas.py
"""Unified Pydantic v2 schemas for all API endpoints."""
import datetime as dt
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

VALID_ROLES = ("citizen", "helper", "officer", "admin", "auditor")
ALLOWED_SIGNUP_ROLES = ("citizen", "helper")


# =====================================================================
# Auth Schemas
# =====================================================================
class RegisterIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    full_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(default=None, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = "citizen"


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6)
    phone: str = ""
    role: str = "citizen"


class LoginIn(BaseModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = ""
    full_name: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    username: Optional[str] = ""
    role: str
    is_active: bool
    created_at: Optional[dt.datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    name: Optional[str] = None


class TokenOut(BaseModel):
    token: str
    role: str
    name: str
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserOut] = None


class OfficerOnlyOut(BaseModel):
    ok: bool
    message: str


# =====================================================================
# Consent Schemas
# =====================================================================
class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sharing_enabled: bool
    shared_with: List[str]
    version: int
    granted_at: dt.datetime
    updated_at: dt.datetime
    withdrawn_at: Optional[dt.datetime] = None


class SharingUpdateIn(BaseModel):
    shared_with: List[str] = Field(default_factory=list)


class AccessEntry(BaseModel):
    actor_role: str
    count: int
    last_at: dt.datetime
    actions: List[str]


class AccessSummary(BaseModel):
    citizen_id: int
    total_access_events: int
    by_role: List[AccessEntry]


class ConsentDetailOut(BaseModel):
    consent: ConsentOut
    who_accessed: AccessSummary


class ConsentIn(BaseModel):
    consent_type: str = "data_processing"  # data_processing, ai_analysis, contact
    granted: bool = True


class ConsentRecordOut(BaseModel):
    id: int
    citizen_id: int
    consent_type: str = "data_processing"
    granted: bool = True
    granted_at: dt.datetime
    revoked_at: Optional[dt.datetime] = None
    ip_hash: str = ""

    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# Case Schemas
# =====================================================================
class CaseCreate(BaseModel):
    title: Optional[str] = "Suspicious Message"
    citizen_id: Optional[int] = None
    channel: str = "sms"
    type: str = "suspicious_sms"
    priority: int = 1
    raw_text: Optional[str] = None
    body_text: Optional[str] = None
    sender_number: Optional[str] = None


class CaseIn(BaseModel):
    channel: str = "sms"
    content: str


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    citizen_id: Optional[int] = None
    channel: str = "sms"
    status: str
    title: str
    priority: Optional[int] = 1
    risk_level: Optional[str] = "medium"
    created_at: dt.datetime


class DecisionCreate(BaseModel):
    label: str  # scam, genuine, complaint, service_request
    confidence: float
    route: str = "auto_handle"
    explanation_ur: Optional[str] = ""
    explanation_user: Optional[str] = ""
    explanation_audit: Optional[dict] = None
    sources: Optional[dict] = None
    decided_by: str = "officer"


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    label: str
    confidence: float
    route: Optional[str] = "auto_handle"
    rule_version_id: Optional[int] = None
    explanation_ur: Optional[str] = ""
    explanation_user: Optional[str] = ""
    decided_by: Optional[str] = "ai_rule_engine"


class CaseDetailOut(BaseModel):
    case: CaseOut
    messages: List[dict] = Field(default_factory=list)
    decision: Optional[DecisionOut] = None


# =====================================================================
# Audit Schemas
# =====================================================================
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    actor_role: str = "citizen"
    action: str
    entity_type: Optional[str] = None
    entity: Optional[str] = None
    entity_id: Optional[int] = None
    detail: dict = Field(default_factory=dict)
    created_at: dt.datetime


class AuditPage(BaseModel):
    items: List[AuditLogOut]
    total: int
    page: int
    page_size: int


class DecisionTraceOut(BaseModel):
    id: int
    case_id: int
    label: str
    confidence: float
    route: str
    explanation_ur: str
    explanation_audit: dict = Field(default_factory=dict)
    sources: dict = Field(default_factory=dict)
    rule_version: Optional[dict] = None
    decided_by: str = "ai_rule_engine"
    created_at: dt.datetime


class AuditEntry(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_role: str
    action: str
    entity: str
    entity_id: Optional[int] = None
    detail: dict = Field(default_factory=dict)
    created_at: dt.datetime


class AuditListOut(BaseModel):
    entries: List[AuditEntry]
    total: int
