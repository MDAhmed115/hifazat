# backend/app/routers/mock_services.py
"""Mock public services (NADRA, Raast, SMS) + fake relief schemes.

PROTOTYPE: every response here is fake data. No real government, banking
or SMS service is ever contacted.

The three POST endpoints all behave the same way:
  - require login (any role; RBAC for sensitive actions lives in other routers),
  - simulate a 1.5s processing delay with asyncio.sleep,
  - write one audit_log row through the shared log_action() helper.
GET /api/mock/schemes is public, read-only, so no audit row is needed.
"""
import asyncio
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import log_action
from ..auth import get_current_user
from ..database import get_db
from ..models import Notification, User

router = APIRouter(prefix="/api/mock", tags=["mock-services"])

CNIC_REGEX = re.compile(r"^\d{5}-\d{7}-\d$")
PHONE_REGEX = re.compile(r"^\+?\d{9,14}$")
SIMULATED_DELAY_SECONDS = 1.5

# Fixed list of FAKE names. The name returned for a CNIC is deterministic
# (same CNIC -> same fake name) so repeated demo calls look consistent.
FAKE_NADRA_NAMES = [
    "Muhammad Bilal",
    "Ayesha Siddiqui",
    "Abdul Rehman",
    "Zainab Fatima",
    "Usman Ghani",
    "Hina Raza",
    "Imran Qureshi",
    "Sana Malik",
]

# GET /api/mock/schemes - 5 fake relief schemes. The "never_asks_money" flag
# is the anti-scam message Hifazat shows citizens next to every scheme.
MOCK_SCHEMES = [
    {
        "id": 1,
        "name": "BISP Kafalat New Qist (Mock 2026)",
        "eligibility": "Monthly household income below PKR 40,000 and a valid CNIC",
        "amount_pkr_mock": 13500,
        "never_asks_money": True,
        "note": "PROTOTYPE: fake scheme, for demo only",
    },
    {
        "id": 2,
        "name": "Ehsaas Emergency Cash (Mock)",
        "eligibility": "Flood-affected families registered in any district",
        "amount_pkr_mock": 25000,
        "never_asks_money": True,
        "note": "PROTOTYPE: fake scheme, for demo only",
    },
    {
        "id": 3,
        "name": "Punjab Kisaan Relief Package (Mock)",
        "eligibility": "Small farmers owning less than 5 acres of land",
        "amount_pkr_mock": 50000,
        "never_asks_money": True,
        "note": "PROTOTYPE: fake scheme, for demo only",
    },
    {
        "id": 4,
        "name": "Sindh Flood Rehabilitation Grant (Mock)",
        "eligibility": "Houses damaged in the 2025 floods with a verified CNIC",
        "amount_pkr_mock": 75000,
        "never_asks_money": True,
        "note": "PROTOTYPE: fake scheme, for demo only",
    },
    {
        "id": 5,
        "name": "Sehat Sahulat Card Plus (Mock)",
        "eligibility": "All families with a poverty score under 40",
        "amount_pkr_mock": 0,
        "never_asks_money": True,
        "note": "PROTOTYPE: fake scheme, for demo only",
    },
]


class NadraIn(BaseModel):
    cnic: str = Field(description="CNIC in the format 42101-1234567-1")


class RaastIn(BaseModel):
    from_cnic: str = Field(description="Sender CNIC, format 42101-1234567-1")
    to_cnic: str = Field(description="Receiver CNIC, format 42101-1234567-1")
    amount: float = Field(gt=0, description="Amount in PKR, must be positive")


class SmsIn(BaseModel):
    phone: str = Field(description="Recipient phone, e.g. 03001234567 or +923001234567")
    body: str = Field(min_length=1, max_length=1000, description="SMS text")


def _validate_cnic(cnic: str) -> None:
    """Reject anything that is not exactly 5-7-1 digits with dashes."""
    if not CNIC_REGEX.match(cnic or ""):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CNIC must match the format 42101-1234567-1 (5 digits, dash, 7 digits, dash, 1 digit)",
        )


@router.post("/nadra")
async def nadra_verify(
    payload: NadraIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Simulated NADRA identity check. NEVER returns real data.

    Mock verification rule: the CNIC counts as verified when its last digit
    is even. The fake name is derived from the CNIC digits, so the same CNIC
    always gets the same fake name during a demo.
    """
    _validate_cnic(payload.cnic)
    await asyncio.sleep(SIMULATED_DELAY_SECONDS)  # pretend to call the government system

    digits = payload.cnic.replace("-", "")
    fake_name = FAKE_NADRA_NAMES[int(digits) % len(FAKE_NADRA_NAMES)]
    verified = int(payload.cnic[-1]) % 2 == 0

    log_action(
        db,
        actor_id=current_user.id,
        action="mock.nadra_verify",
        entity_type=None,
        entity_id=None,
        details={"cnic": payload.cnic, "verified": verified, "caller_user_id": current_user.id},
    )
    return {
        "cnic": payload.cnic,
        "name": fake_name,
        "verified": verified,
        "source": "MOCK NADRA - PROTOTYPE, not real data",
    }


@router.post("/raast")
async def raast_transfer(
    payload: RaastIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Simulated Raast transfer. Money never actually moves."""
    _validate_cnic(payload.from_cnic)
    _validate_cnic(payload.to_cnic)
    await asyncio.sleep(SIMULATED_DELAY_SECONDS)  # pretend to talk to the payment rail

    txn_id = "MOCK-" + uuid.uuid4().hex[:8].upper()

    log_action(
        db,
        actor_id=current_user.id,
        action="mock.raast_transfer",
        entity_type=None,
        entity_id=None,
        details={
            "txn_id": txn_id,
            "from_cnic": payload.from_cnic,
            "to_cnic": payload.to_cnic,
            "amount_pkr": payload.amount,
        },
    )
    return {"txn_id": txn_id, "status": "pending", "note": "simulated"}


@router.post("/sms/send")
async def sms_send(
    payload: SmsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Simulated SMS gateway: stores one notifications row instead of really sending.

    If the phone belongs to a registered user, the notification is linked to
    that user so it can appear in their notification list later.
    """
    phone = payload.phone.strip()
    if not PHONE_REGEX.match(phone):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="phone must look like 03001234567 or +923001234567 (9-14 digits, optional leading +)",
        )
    await asyncio.sleep(SIMULATED_DELAY_SECONDS)  # pretend to send through an SMS gateway

    recipient = db.query(User).filter(User.phone == phone).first()
    notification = Notification(
        user_id=recipient.id if recipient else None,
        case_id=None,
        channel="sms",
        body=payload.body,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    log_action(
        db,
        actor_id=current_user.id,
        action="mock.sms_send",
        entity_type="notifications",
        entity_id=notification.id,
        details={"phone": phone, "body_chars": len(payload.body)},
    )
    return {
        "sent": True,
        "notification_id": notification.id,
        "recipient": phone,
        "note": "PROTOTYPE: stored in the notifications table, not really sent",
    }


@router.get("/schemes")
def list_schemes():
    """Public list of 5 FAKE relief schemes (read-only, no login needed).

    Every scheme carries never_asks_money=true because a real relief
    programme never charges citizens to receive their payment.
    """
    return list(MOCK_SCHEMES)
