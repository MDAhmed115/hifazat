# backend/app/models.py
"""All 10 unified SQLAlchemy models combining p4, p5, and p6 features."""
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# =====================================================================
# 1. User
# =====================================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    full_name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[Optional[str]] = mapped_column(String(30), unique=True, index=True, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), unique=True, index=True, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="citizen")  # citizen, helper, officer, admin, auditor
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    citizen_profile: Mapped[Optional["Citizen"]] = relationship(
        "Citizen", back_populates="user", uselist=False, foreign_keys="Citizen.user_id"
    )

    @property
    def display_name(self) -> str:
        return self.name or self.full_name or self.username or self.phone or self.email or f"User-{self.id}"


# =====================================================================
# 2. Citizen
# =====================================================================
class Citizen(Base):
    __tablename__ = "citizens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    helper_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    cnic: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True, nullable=True)
    cnic_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    cnic_masked: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    name_key: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)  # fuzzy name matching
    district: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="ur")
    language_pref: Mapped[str] = mapped_column(String(10), default="ur")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="citizen_profile", foreign_keys=[user_id])
    consents: Mapped[list["Consent"]] = relationship("Consent", back_populates="citizen")
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="citizen")


# =====================================================================
# 3. Consent
# =====================================================================
class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    citizen_id: Mapped[int] = mapped_column(ForeignKey("citizens.id"), index=True)

    # P5 Data sharing & withdrawal model
    sharing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    shared_with: Mapped[str] = mapped_column(String(255), default='["helper"]')  # JSON list string
    version: Mapped[int] = mapped_column(Integer, default=1)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # P4 & P6 Event-based consent attributes
    purpose: Mapped[str] = mapped_column(String(120), default="anti_scam_assistance")
    consent_type: Mapped[str] = mapped_column(String(40), default="data_processing")  # data_processing, ai_analysis, contact
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_hash: Mapped[str] = mapped_column(String(64), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    citizen: Mapped["Citizen"] = relationship("Citizen", back_populates="consents")


# =====================================================================
# 4. Case
# =====================================================================
class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    citizen_id: Mapped[Optional[int]] = mapped_column(ForeignKey("citizens.id"), index=True, nullable=True)
    opened_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_officer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(200), default="Suspicious Message")
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(40), default="suspicious_sms")
    channel: Mapped[str] = mapped_column(String(30), default="sms")  # sms, whatsapp, voice, document
    status: Mapped[str] = mapped_column(String(30), default="open")  # open, in_review, with_officer, auto_handled, resolved, rejected
    priority: Mapped[int] = mapped_column(Integer, default=1)  # 1-10 priority score
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    citizen: Mapped[Optional["Citizen"]] = relationship("Citizen", back_populates="cases")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="case", cascade="all, delete-orphan")
    decisions: Mapped[list["Decision"]] = relationship("Decision", back_populates="case", cascade="all, delete-orphan")


# =====================================================================
# 5. Message
# =====================================================================
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30), default="sms")
    sender_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    sender_role: Mapped[str] = mapped_column(String(20), default="citizen")
    sender_label: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extracted_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped["Case"] = relationship("Case", back_populates="messages")

    @property
    def body(self) -> str:
        return self.body_text or self.raw_text or self.ocr_text or ""


# =====================================================================
# 6. Decision
# =====================================================================
class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    label: Mapped[str] = mapped_column(String(40), default="scam")  # scam, genuine, complaint, service_request
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    route: Mapped[str] = mapped_column(String(40), default="auto_handle")  # auto_handle, ask_more_proof, human_handoff

    explanation_ur: Mapped[str] = mapped_column(Text, default="")
    explanation_user: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation_audit: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(60), default="ai_rule_engine")
    model_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    trace_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    rule_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rule_versions.id"), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped["Case"] = relationship("Case", back_populates="decisions")
    rule_version: Mapped[Optional["RuleVersion"]] = relationship("RuleVersion")

    @property
    def created_at(self) -> datetime:
        return self.decided_at


# =====================================================================
# 7. RuleVersion
# =====================================================================
class RuleVersion(Base):
    __tablename__ = "rule_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    version: Mapped[str] = mapped_column(String(30), default="v1.0")
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    thresholds: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rules_json: Mapped[dict] = mapped_column(JSON, default=dict)
    changed_by: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# =====================================================================
# 8. AuditLog
# =====================================================================
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(40), default="citizen")
    action: Mapped[str] = mapped_column(String(80), index=True)

    entity_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    entity: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON text
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    __table_args__ = (
        Index("ix_audit_entity_lookup", "entity_type", "entity_id"),
    )

    @property
    def actor_user_id(self) -> Optional[int]:
        return self.actor_id

    @property
    def detail(self) -> dict:
        try:
            return json.loads(self.details) if self.details else {}
        except Exception:
            return {}


# =====================================================================
# 9. ScamPattern
# =====================================================================
class ScamPattern(Base):
    __tablename__ = "scam_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pattern_text: Mapped[str] = mapped_column(Text)
    pattern: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="relief_payment")
    pattern_type: Mapped[str] = mapped_column(String(40), default="sms_scam")
    label: Mapped[str] = mapped_column(String(40), default="scam")
    risk_weight: Mapped[float] = mapped_column(Float, default=0.8)
    severity: Mapped[float] = mapped_column(Float, default=0.8)
    language: Mapped[str] = mapped_column(String(10), default="ur")
    area: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    reported_count: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# =====================================================================
# 10. Notification
# =====================================================================
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(120), default="Case Update")
    channel: Mapped[str] = mapped_column(String(20), default="app")
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
