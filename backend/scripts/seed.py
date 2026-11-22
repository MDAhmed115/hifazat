# backend/scripts/seed.py
"""Comprehensive unified seed script combining all demo datasets from P4, P5, and P6.
Seeds all 5 roles, multiple citizens, active cases, messages, decisions with Urdu text,
rule versions, scam patterns, notifications, and audit log entries.
"""
import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.audit import log_action
from app.database import Base, SessionLocal, engine, utcnow
from app.models import (
    AuditLog,
    Case,
    Citizen,
    Consent,
    Decision,
    Message,
    Notification,
    RuleVersion,
    ScamPattern,
    User,
)
from app.security import hash_password

DEFAULT_PASSWORD = "Password123!"

DEMO_USERS = [
    {
        "name": "Hifazat Admin",
        "full_name": "Hifazat Admin",
        "phone": "03000000000",
        "email": "admin@example.com",
        "username": "admin1",
        "role": "admin",
        "password": "admin123",
    },
    {
        "name": "Yaman Ayyubi",
        "full_name": "Colonel Yaman Ayyubi",
        "phone": "03000000101",
        "email": "officer@example.com",
        "username": "officer1",
        "role": "officer",
        "password": "officer123",
    },
    {
        "name": "Azban Qaseem",
        "full_name": "Inspector Azban Qaseem",
        "phone": "03000000102",
        "email": "imran@example.com",
        "username": "officer2",
        "role": "officer",
        "password": "officer123",
    },
    {
        "name": "Kamran Ali",
        "full_name": "Kamran Ali (Helper)",
        "phone": "03000000201",
        "email": "bilal@example.com",
        "username": "helper1",
        "role": "helper",
        "password": "helper123",
    },
    {
        "name": "Muhammad Ashraf",
        "full_name": "Muhammad Ashraf",
        "phone": "03000000301",
        "email": "ashraf@example.com",
        "username": "citizen1",
        "role": "citizen",
        "password": "citizen123",
    },
    {
        "name": "Ayesha Khan",
        "full_name": "Ayesha Khan",
        "phone": "03000000302",
        "email": "ayesha@example.com",
        "username": "ayesha",
        "role": "citizen",
        "password": "Demo@1234",
    },
    {
        "name": "Faiq Auditor",
        "full_name": "Faiq Auditor",
        "phone": "03000000401",
        "email": "auditor@example.com",
        "username": "auditor1",
        "role": "auditor",
        "password": "auditor123",
    },
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(User).filter(User.phone == "03000000000").first():
            print("[seed] Database already seeded. Skipping initial user creation.")
            return

        print("[seed] Seeding database with unified demo data...")

        # 1. Users
        created_users = {}
        for u_data in DEMO_USERS:
            pw = u_data.get("password") or DEFAULT_PASSWORD
            u = User(
                name=u_data["name"],
                full_name=u_data["full_name"],
                phone=u_data["phone"],
                email=u_data["email"],
                username=u_data["username"],
                hashed_password=hash_password(pw),
                role=u_data["role"],
                is_active=True,
            )
            db.add(u)
            db.flush()
            created_users[u_data["username"]] = u

        # 2. Rule Versions
        rv1 = RuleVersion(
            version="v1.0",
            version_no=1,
            description="Baseline scam classification and relief scheme thresholds",
            thresholds={"auto": 0.85, "ask": 0.60, "high_risk_kw": ["OTP", "PIN", "send money"]},
            rules_json={
                "auto_handle_threshold": 0.85,
                "ask_proof_threshold": 0.60,
                "high_risk_keywords": ["OTP", "PIN", "password", "send money", "Bait-ul-Maal"],
            },
            active=True,
        )
        db.add(rv1)
        db.flush()

        # 3. Citizens
        helper = created_users.get("helper1")
        c1 = created_users.get("citizen1")
        c2 = created_users.get("ayesha")

        cit1 = Citizen(
            user_id=c1.id,
            helper_id=helper.id if helper else None,
            cnic="42101-1234567-1",
            cnic_last4="4567",
            cnic_masked="42101-*****67-1",
            full_name=c1.full_name,
            district="Karachi Central",
            city="Karachi",
            language="ur",
        )
        cit2 = Citizen(
            user_id=c2.id,
            helper_id=helper.id if helper else None,
            cnic="42101-7654321-2",
            cnic_last4="4321",
            cnic_masked="42101-*****21-2",
            full_name=c2.full_name,
            district="Lahore Cantt",
            city="Lahore",
            language="ur",
        )
        db.add_all([cit1, cit2])
        db.flush()

        # 4. Consents
        cons1 = Consent(
            citizen_id=cit1.id,
            sharing_enabled=True,
            shared_with='["helper", "officer"]',
            version=1,
            purpose="relief_payment_verification",
        )
        cons2 = Consent(
            citizen_id=cit2.id,
            sharing_enabled=True,
            shared_with='["helper"]',
            version=1,
            purpose="sms_fraud_investigation",
        )
        db.add_all([cons1, cons2])
        db.flush()

        # 5. Cases & Messages
        case1 = Case(
            citizen_id=cit1.id,
            opened_by=c1.id,
            title="Fake Bait-ul-Maal Relief SMS",
            type="suspicious_sms",
            channel="sms",
            status="open",
            priority=8,
            risk_level="high",
            raw_content="Congratulations! Aap ne Bait-ul-Maal Relief jeeta hai. Rs 250,000 prize claim karne ke liye Rs 250 processing fee Raast karein: 0300-7788990",
        )
        case2 = Case(
            citizen_id=cit2.id,
            opened_by=c2.id,
            title="BISP 8500 Payment Verification",
            type="service_request",
            channel="whatsapp",
            status="resolved",
            priority=3,
            risk_level="low",
            raw_content="Your BISP payment of Rs 8500 is ready at the camp office. Bring your CNIC on Friday 10am-2pm.",
        )
        db.add_all([case1, case2])
        db.flush()

        m1 = Message(
            case_id=case1.id,
            channel="sms",
            sender_number="0300-7788990",
            sender_role="citizen",
            body_text=case1.raw_content,
            raw_text=case1.raw_content,
        )
        m2 = Message(
            case_id=case2.id,
            channel="whatsapp",
            sender_number="8171",
            sender_role="citizen",
            body_text=case2.raw_content,
            raw_text=case2.raw_content,
        )
        db.add_all([m1, m2])
        db.flush()

        # 6. Decisions
        dec1 = Decision(
            case_id=case1.id,
            label="scam",
            confidence=0.94,
            route="auto_handle",
            explanation_ur="یہ پیغام جعلی ہے۔ حکومت یا بیت المال کبھی انعامی رقم سے پہلے فیس یا ایڈوانس رقم کا مطالبہ نہیں کرتی۔",
            explanation_user="یہ پیغام جعلی ہے۔ حکومت یا بیت المال کبھی انعامی رقم سے پہلے فیس یا ایڈوانس رقم کا مطالبہ نہیں کرتی۔",
            explanation_audit={
                "model": "llama-3.3-70b-versatile",
                "reasoning": "Advance fee scam targeting Pakistani relief programs with personal mobile number transfer request.",
                "signals": ["advance_fee_requested", "fake_government_scheme"],
            },
            sources={"scheme_catalog": "Bait-ul-Maal Official Advisory 2026"},
            rule_version_id=rv1.id,
            decided_by="ai_rule_engine",
        )
        dec2 = Decision(
            case_id=case2.id,
            label="genuine",
            confidence=0.91,
            route="auto_handle",
            explanation_ur="یہ پیغام BISP کا سرکاری اعلامیہ ہے۔ مقررہ تاریخ پر قریبی کیمپ تشریف لے جائیں اور شناختی کارڈ ساتھ رکھیں۔",
            explanation_user="یہ پیغام BISP کا سرکاری اعلامیہ ہے۔ مقررہ تاریخ پر قریبی کیمپ تشریف لے جائیں اور شناختی کارڈ ساتھ رکھیں۔",
            explanation_audit={
                "model": "llama-3.3-70b-versatile",
                "reasoning": "Official 8171 notification without fee request or external payment link.",
            },
            sources={"bisp_registry": "8171 Official Shortcode"},
            rule_version_id=rv1.id,
            decided_by="ai_rule_engine",
        )
        db.add_all([dec1, dec2])
        db.flush()

        # 7. Scam Patterns
        pats = [
            ScamPattern(pattern_text="Bait-ul-Maal Relief advance fee scam", category="relief_payment", severity=0.9),
            ScamPattern(pattern_text="Ehsaas Program lottery winner OTP phishing", category="lottery", severity=0.95),
            ScamPattern(pattern_text="Electricity bill fake disconnection warning", category="utility", severity=0.7),
        ]
        db.add_all(pats)

        # 8. Initial Audit Log Entries
        log_action(db, actor_id=created_users["admin1"].id, actor_role="admin", action="system.initialized", entity_type="system", details={"version": "1.0"})
        log_action(db, actor_id=c1.id, actor_role="citizen", action="case.created", entity_type="case", entity_id=case1.id, details={"title": case1.title})
        log_action(db, actor_id=None, actor_role="ai_engine", action="decision.recorded", entity_type="decision", entity_id=dec1.id, details={"label": "scam", "confidence": 0.94})

        db.commit()
        print("==================================================================")
        print("HIFAZAT UNIFIED SEED COMPLETE")
        print("Demo Logins (phone / password):")
        print("  Admin:    03000000000 / admin123")
        print("  Officer:  03000000101 / officer123")
        print("  Helper:   03000000201 / helper123")
        print("  Citizen:  03000000301 / citizen123")
        print("  Auditor:  03000000401 / auditor123")
        print("==================================================================")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
