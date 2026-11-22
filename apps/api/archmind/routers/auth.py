import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from archmind.db import get_db
from archmind.models import AuditEvent, AuthSession, LoginAttempt, Membership, User
from archmind.security import (
    COOKIE,
    DUMMY_HASH,
    Principal,
    audit,
    client_key,
    cookie_kwargs,
    current,
    hash_password,
    locked_out,
    new_session,
    verify_password,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])

Role = Literal["admin", "project_manager", "reviewer", "contributor", "viewer"]


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class Me(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    org_id: uuid.UUID
    role: str


class UserIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    role: Role
    temporary_password: str = Field(min_length=12)


@router.post("/auth/login", response_model=Me)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> Me:
    email = body.email.lower()
    ip = client_key(request.client.host if request.client else None)
    if locked_out(db, email, ip):
        raise HTTPException(429, "too many failed attempts; try again in 15 minutes")
    user = db.scalar(select(User).where(User.email == email))
    m = db.scalar(select(Membership).where(Membership.user_id == user.id)) if user else None
    # Always run one argon2 verify so unknown emails take as long as wrong passwords.
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if user is None or not user.active or m is None or not ok:
        db.add(LoginAttempt(email=email, ip=ip, ok=False))
        audit(db, "auth.login_failed", None, None, email)
        db.commit()
        raise HTTPException(401, "wrong email or password")
    db.add(LoginAttempt(email=email, ip=ip, ok=True))
    token = new_session(db, user.id, m.org_id)
    audit(db, "auth.login", m.org_id, user.id)
    db.commit()
    response.set_cookie(COOKIE, token, **cookie_kwargs())  # type: ignore[arg-type]
    return Me(id=user.id, email=user.email, name=user.name, org_id=m.org_id, role=m.role)


@router.post("/auth/logout", status_code=204)
def logout(response: Response, p: Principal = Depends(current), db: Session = Depends(get_db)) -> None:
    s = db.get(AuthSession, p.session_id)
    if s:
        s.revoked = True
    audit(db, "auth.logout", p.org_id, p.user.id)
    db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=Me)
def me(p: Principal = Depends(current)) -> Me:
    return Me(id=p.user.id, email=p.user.email, name=p.user.name, org_id=p.org_id, role=p.role)


@router.post("/users", response_model=Me, status_code=201)
def create_user(body: UserIn, p: Principal = Depends(current), db: Session = Depends(get_db)) -> Me:
    p.require("manage_users")
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "email already registered")
    u = User(email=email, name=body.name, password_hash=hash_password(body.temporary_password))
    db.add(u)
    db.flush()
    db.add(Membership(org_id=p.org_id, user_id=u.id, role=body.role))
    audit(db, "user.create", p.org_id, p.user.id, str(u.id), role=body.role)
    db.commit()
    return Me(id=u.id, email=u.email, name=u.name, org_id=p.org_id, role=body.role)


class AuditOut(BaseModel):
    action: str
    target: str
    actor_id: uuid.UUID | None
    at: str


@router.get("/audit", response_model=list[AuditOut])
def audit_log(p: Principal = Depends(current), db: Session = Depends(get_db)) -> list[AuditOut]:
    p.require("manage_users")
    rows = db.scalars(
        select(AuditEvent).where(AuditEvent.org_id == p.org_id).order_by(AuditEvent.at.desc()).limit(200)
    )
    return [
        AuditOut(action=r.action, target=r.target, actor_id=r.actor_id, at=r.at.isoformat()) for r in rows
    ]
