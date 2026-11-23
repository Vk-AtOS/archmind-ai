"""Passwords, sessions, login throttling and role checks (ADR-002)."""

import hashlib
import ipaddress
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from archmind.config import settings
from archmind.db import get_db, utcnow
from archmind.models import AuditEvent, AuthSession, LoginAttempt, Membership, User

COOKIE = "am_session"
SESSION_TTL = timedelta(hours=12)
MAX_FAILURES_PER_IP = 5  # per account and client network: stops guessing from one place
MAX_FAILURES_PER_ACCOUNT = 20  # all networks: caps distributed guessing at 80/hour per account,
# while one attacker alone can no longer lock a victim out with five bad passwords.
LOCKOUT = timedelta(minutes=15)
TRUSTED_FOR = timedelta(days=30)


def client_key(host: str | None) -> str:
    """Throttle key: IPv4 address, or the /64 network for IPv6 (one host usually owns a whole /64).
    Behind a reverse proxy, uvicorn must run with --forwarded-allow-ips set to that proxy only (ARCH-108)."""
    if not host:
        return "unknown"
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return host[:64]
    if addr.version == 6:
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


_ph = PasswordHasher()
DUMMY_HASH = _ph.hash("timing-equaliser-not-a-real-password")

# Write permissions per role; every role can read within its organisation.
CAN = {
    "manage_users": {"admin"},
    "create_project": {"admin", "project_manager"},
    "create_brief": {"admin", "project_manager", "contributor"},
    "rate_layout": {"admin", "project_manager", "reviewer"},
}


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(hashed: str, pw: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except VerifyMismatchError:
        return False


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def locked_out(db: Session, email: str, ip: str) -> bool:
    # ponytail: count-then-insert is not atomic, so a burst can exceed the limit by a few tries;
    # use a per-key counter (Redis INCR) if that margin ever matters.
    since = utcnow() - LOCKOUT
    failed = (LoginAttempt.email == email, LoginAttempt.ok.is_(False), LoginAttempt.at > since)
    per_ip = db.scalar(select(func.count()).where(*failed, LoginAttempt.ip == ip)) or 0
    if per_ip >= MAX_FAILURES_PER_IP:
        return True
    # A network this user signed in from recently gets double the account-wide allowance, so an
    # attacker spraying from elsewhere does not lock the real user out of their usual network
    # first. ponytail: network-based trust; a signed known-device cookie is stronger (ARCH-27 follow-up).
    trusted = ip != "unknown" and bool(
        db.scalar(
            select(func.count()).where(
                LoginAttempt.email == email,
                LoginAttempt.ip == ip,
                LoginAttempt.ok.is_(True),
                LoginAttempt.at > utcnow() - TRUSTED_FOR,
            )
        )
    )
    cap = MAX_FAILURES_PER_ACCOUNT * (2 if trusted else 1)
    per_account = db.scalar(select(func.count()).where(*failed)) or 0
    return per_account >= cap


def new_session(db: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=_digest(token), user_id=user_id, org_id=org_id, expires_at=utcnow() + SESSION_TTL
        )
    )
    return token


def cookie_kwargs() -> dict[str, object]:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.env != "dev",
        "max_age": int(SESSION_TTL.total_seconds()),
        "path": "/",
    }


@dataclass(frozen=True)
class Principal:
    user: User
    org_id: uuid.UUID
    role: str
    session_id: uuid.UUID

    def require(self, permission: str) -> None:
        if self.role not in CAN[permission]:
            raise HTTPException(403, f"role '{self.role}' cannot {permission.replace('_', ' ')}")


def current(
    request: Request, db: Session = Depends(get_db), am_session: str | None = Cookie(default=None)
) -> Principal:
    if not am_session:
        raise HTTPException(401, "not signed in")
    s = db.scalar(select(AuthSession).where(AuthSession.token_hash == _digest(am_session)))
    if s is None or s.revoked or s.expires_at.replace(tzinfo=utcnow().tzinfo) < utcnow():
        raise HTTPException(401, "session expired")
    user = db.get(User, s.user_id)
    m = db.scalar(select(Membership).where(Membership.user_id == s.user_id, Membership.org_id == s.org_id))
    if user is None or not user.active or m is None:
        raise HTTPException(401, "account disabled")
    # CSRF: cookies are SameSite=Lax and mutating routes accept JSON only, which a cross-site
    # form cannot send without a CORS preflight (no CORS is enabled).
    if request.method not in ("GET", "HEAD") and "application/json" not in request.headers.get(
        "content-type", ""
    ):
        raise HTTPException(415, "JSON body required")
    return Principal(user=user, org_id=s.org_id, role=m.role, session_id=s.id)


def audit(
    db: Session,
    action: str,
    org_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    target: str = "",
    **meta: object,
) -> None:
    db.add(AuditEvent(org_id=org_id, actor_id=actor_id, action=action, target=target, meta=meta))
