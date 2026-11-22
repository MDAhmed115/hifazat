# backend/app/deps.py
"""FastAPI dependencies: current user, role checking, own-citizen lookup."""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import Citizen, Consent, User
from .security import get_current_user, require_role


def get_own_citizen(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, Citizen]:
    """For citizen endpoints: returns (User, Citizen), auto-seeding a default citizen & consent if needed."""
    if user.role != "citizen":
        raise HTTPException(status_code=403, detail="Citizen role required")

    citizen = db.query(Citizen).filter(Citizen.user_id == user.id).first()
    if citizen is None:
        citizen = Citizen(
            user_id=user.id,
            cnic=f"42101-{user.id:07d}-1",
            cnic_last4=f"{user.id % 10000:04d}",
            full_name=user.name or user.full_name or "Citizen User",
            district="Karachi Central",
            city="Karachi",
            language="ur",
        )
        db.add(citizen)
        db.flush()

    # Ensure consent row exists
    consent = db.query(Consent).filter(Consent.citizen_id == citizen.id).first()
    if consent is None:
        consent = Consent(
            citizen_id=citizen.id,
            sharing_enabled=True,
            shared_with='["helper"]',
            version=1,
        )
        db.add(consent)

    db.commit()
    db.refresh(citizen)
    return user, citizen
