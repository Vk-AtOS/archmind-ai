"""Persistence model (ARCH-27, 28, 33, 35). Every project-scoped row carries org_id for tenant checks."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from archmind.db import Base, utcnow

ROLES = ("admin", "project_manager", "reviewer", "contributor", "viewer")


def _id() -> uuid.UUID:
    return uuid.uuid4()


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # Opt-in to share actual costs and project data for estimate improvement (ARCH-145). Off by default.
    data_use_opt_in: Mapped[bool] = mapped_column(default=False, server_default="false")


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(32))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 of the cookie value
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    revoked: Mapped[bool] = mapped_column(default=False)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_email_at", "email", "at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String(320))
    ip: Mapped[str] = mapped_column(String(64), default="")
    ok: Mapped[bool]
    at: Mapped[datetime] = mapped_column(default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(300), default="")
    rule_pack: Mapped[str] = mapped_column(String(100), default="generic-metric-v0")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Brief(Base):
    """Immutable once stored: a changed brief is a new row (revision history)."""

    __tablename__ = "briefs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class DesignOption(Base):
    __tablename__ = "design_options"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    brief_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("briefs.id"), index=True)
    label: Mapped[str] = mapped_column(String(50))
    layout: Mapped[dict[str, Any]] = mapped_column(JSON)
    score: Mapped[float]
    generator_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AuditEvent(Base):
    """Append-only (ARCH-33). The application never updates or deletes rows here."""

    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    org_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(200), default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(default=utcnow)


class ActualCost(Base):
    """Builder-reported actual cost for a chosen option (ARCH-154). Append-only: a correction is a new row."""

    __tablename__ = "actual_costs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    option_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("design_options.id"), index=True)
    total: Mapped[float]
    currency: Mapped[str] = mapped_column(String(3))
    estimate_total: Mapped[
        float
    ]  # estimate at the time of recording, so later rate changes do not rewrite history
    rate_table: Mapped[str] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(String(1000), default="")
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    at: Mapped[datetime] = mapped_column(default=utcnow)


class LayoutRating(Base):
    """Architect rating of a generated option (ARCH-155). One current rating per rater per option."""

    __tablename__ = "layout_ratings"
    __table_args__ = (UniqueConstraint("option_id", "rater_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_id)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    option_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("design_options.id"), index=True)
    rater_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    usability: Mapped[int]
    circulation: Mapped[int]
    daylight: Mapped[int]
    buildability: Mapped[int]
    client_ready: Mapped[int]
    comment: Mapped[str] = mapped_column(String(2000), default="")
    generator_version: Mapped[str] = mapped_column(String(20))
    at: Mapped[datetime] = mapped_column(default=utcnow)


class OptionInterior(Base):
    """Saved interior design of an option (ARCH-156): finishes and placed items, one per option.
    revision guards against two people overwriting each other's edits."""

    __tablename__ = "option_interiors"
    option_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("design_options.id"), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    catalog_version: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(default=1)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)
