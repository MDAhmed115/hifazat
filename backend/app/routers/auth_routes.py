# backend/app/routers/auth_routes.py
"""Unified Authentication router supporting phone, email, and username logins."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..audit import log_action
from ..database import get_db
from ..models import Citizen, Consent, User
from ..schemas import LoginIn, RegisterIn, Token, TokenOut, UserOut, VALID_ROLES
from ..security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """Register or sign up a new user (supports phone, email, or username)."""
    if payload.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Role must be one of: {', '.join(VALID_ROLES)}",
        )

    # Protect admin registration if an admin already exists
    if payload.role == "admin" and db.query(User).filter(User.role == "admin").count() > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin registration is closed: a bootstrap admin already exists",
        )

    # Check unique constraints
    if payload.phone and db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")
    if payload.email and db.query(User).filter(User.email == str(payload.email)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if payload.username and db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already registered")

    disp_name = payload.name or payload.full_name or payload.username or payload.phone or str(payload.email) or "New User"

    user = User(
        name=disp_name,
        full_name=disp_name,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Automatically initialize Citizen + Consent records for citizen signups
    if user.role == "citizen":
        cit = Citizen(
            user_id=user.id,
            cnic=f"42101-{user.id:07d}-1",
            cnic_last4=f"{user.id % 10000:04d}",
            full_name=disp_name,
            district="Karachi Central",
            city="Karachi",
            language="ur",
        )
        db.add(cit)
        db.flush()

        cons = Consent(
            citizen_id=cit.id,
            sharing_enabled=True,
            shared_with='["helper"]',
            version=1,
            purpose="anti_scam_assistance",
        )
        db.add(cons)
        db.commit()

    log_action(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="user.register",
        entity_type="users",
        entity_id=user.id,
        details={"role": user.role, "phone": user.phone, "email": user.email},
    )
    return user


@router.post("/login", response_model=TokenOut)
async def login(
    request: Request,
    payload: LoginIn = None,
    db: Session = Depends(get_db),
):
    """Login with JSON body or form-data (OAuth2). Accepts phone, email, or username."""
    identifier = ""
    password = ""

    # Check if form data or JSON
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        identifier = form.get("username", "")
        password = form.get("password", "")
    else:
        try:
            body = await request.json()
            identifier = body.get("phone") or body.get("email") or body.get("username") or ""
            password = body.get("password") or ""
        except Exception:
            if payload:
                identifier = payload.phone or payload.email or payload.username or ""
                password = payload.password

    # Find user by phone, email, or username
    user = None
    if identifier:
        user = (
            db.query(User)
            .filter(
                (User.phone == identifier)
                | (User.email == identifier)
                | (User.username == identifier)
            )
            .first()
        )

    if user is None or not verify_password(password, user.hashed_password):
        log_action(db, actor_id=None, action="user.login_failed", details={"identifier": identifier})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is deactivated")

    tok = create_access_token(
        user_id=user.id,
        role=user.role,
        name=user.name or user.full_name,
        username=user.username or "",
    )

    log_action(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="user.login",
        entity_type="users",
        entity_id=user.id,
        details={"role": user.role},
    )

    return TokenOut(
        token=tok,
        access_token=tok,
        token_type="bearer",
        role=user.role,
        name=user.name or user.full_name or "User",
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
