"""Layout quality ratings by architects and reviewers (ARCH-155). Evidence for generator changes."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from archmind.db import get_db, utcnow
from archmind.models import LayoutRating
from archmind.routers.projects import _option
from archmind.security import Principal, audit, current

router = APIRouter(prefix="/api/v1", tags=["ratings"])
CRITERIA = ("usability", "circulation", "daylight", "buildability", "client_ready")


class RatingIn(BaseModel):
    usability: int = Field(ge=1, le=5)
    circulation: int = Field(ge=1, le=5)
    daylight: int = Field(ge=1, le=5)
    buildability: int = Field(ge=1, le=5)
    client_ready: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class RatingOut(RatingIn):
    rater_id: uuid.UUID
    generator_version: str
    at: str


class VersionSummary(BaseModel):
    generator_version: str
    ratings: int
    averages: dict[str, float]


def _out(r: LayoutRating) -> RatingOut:
    return RatingOut(
        **{c: getattr(r, c) for c in CRITERIA},
        comment=r.comment,
        rater_id=r.rater_id,
        generator_version=r.generator_version,
        at=r.at.isoformat(),
    )


@router.put("/options/{option_id}/rating", response_model=RatingOut)
def rate(
    option_id: uuid.UUID, body: RatingIn, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> RatingOut:
    """Create or replace the caller's rating of this option."""
    p.require("rate_layout")
    o, _, _ = _option(db, p, option_id)
    r = db.scalar(
        select(LayoutRating).where(LayoutRating.option_id == o.id, LayoutRating.rater_id == p.user.id)
    )
    if r is None:
        r = LayoutRating(
            org_id=p.org_id, option_id=o.id, rater_id=p.user.id, generator_version=o.generator_version
        )
        db.add(r)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    r.at = utcnow()
    audit(db, "option.rate", p.org_id, p.user.id, str(o.id), **{c: getattr(body, c) for c in CRITERIA})
    db.commit()
    return _out(r)


@router.get("/options/{option_id}/ratings", response_model=list[RatingOut])
def option_ratings(
    option_id: uuid.UUID, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> list[RatingOut]:
    o, _, _ = _option(db, p, option_id)
    return [_out(r) for r in db.scalars(select(LayoutRating).where(LayoutRating.option_id == o.id))]


@router.get("/ratings/summary", response_model=list[VersionSummary])
def summary(p: Principal = Depends(current), db: Session = Depends(get_db)) -> list[VersionSummary]:
    """Average rating per criterion for each generator version in this organisation."""
    cols = [func.avg(getattr(LayoutRating, c)) for c in CRITERIA]
    q = (
        select(LayoutRating.generator_version, func.count(), *cols)
        .where(LayoutRating.org_id == p.org_id)
        .group_by(LayoutRating.generator_version)
        .order_by(LayoutRating.generator_version)
    )
    return [
        VersionSummary(
            generator_version=row[0],
            ratings=row[1],
            averages={c: round(float(v), 2) for c, v in zip(CRITERIA, row[2:], strict=True)},
        )
        for row in db.execute(q)
    ]
