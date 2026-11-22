"""Organisation data-use setting and actual-cost capture (ARCH-154, ARCH-145)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from archmind.db import get_db
from archmind.design.estimate import estimate, load_rates
from archmind.design.quantities import compute
from archmind.models import ActualCost, Organization
from archmind.routers.projects import RATE_TABLE, _option
from archmind.security import Principal, audit, current

router = APIRouter(prefix="/api/v1", tags=["costs"])


class OrgSettings(BaseModel):
    data_use_opt_in: bool


class ActualCostIn(BaseModel):
    total: float = Field(gt=0, le=1e12)
    currency: str = Field(pattern="^[A-Z]{3}$")
    note: str = Field(default="", max_length=1000)


class ActualCostOut(BaseModel):
    id: uuid.UUID
    total: float
    currency: str
    estimate_total: float
    rate_table: str
    error_pct: float  # (estimate - actual) / actual x 100; negative = estimate too low
    note: str
    at: str


def _org(db: Session, p: Principal) -> Organization:
    org = db.get(Organization, p.org_id)
    assert org is not None
    return org


def _out(a: ActualCost) -> ActualCostOut:
    return ActualCostOut(
        id=a.id,
        total=a.total,
        currency=a.currency,
        estimate_total=a.estimate_total,
        rate_table=a.rate_table,
        error_pct=round((a.estimate_total - a.total) / a.total * 100, 1),
        note=a.note,
        at=a.at.isoformat(),
    )


@router.get("/org/settings", response_model=OrgSettings)
def get_settings(p: Principal = Depends(current), db: Session = Depends(get_db)) -> OrgSettings:
    return OrgSettings(data_use_opt_in=_org(db, p).data_use_opt_in)


@router.put("/org/settings", response_model=OrgSettings)
def put_settings(
    body: OrgSettings, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> OrgSettings:
    p.require("manage_users")
    org = _org(db, p)
    org.data_use_opt_in = body.data_use_opt_in
    audit(db, "org.data_use_opt_in", p.org_id, p.user.id, str(p.org_id), value=body.data_use_opt_in)
    db.commit()
    return OrgSettings(data_use_opt_in=org.data_use_opt_in)


@router.post("/options/{option_id}/actual-costs", response_model=ActualCostOut, status_code=201)
def record_actual(
    option_id: uuid.UUID, body: ActualCostIn, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> ActualCostOut:
    p.require("create_brief")
    o, layout, _ = _option(db, p, option_id)
    if not _org(db, p).data_use_opt_in:
        raise HTTPException(409, "actual-cost capture is off; an admin must enable data use in settings")
    est = estimate(compute(layout), load_rates(RATE_TABLE))
    if body.currency != est.currency:
        raise HTTPException(422, f"currency must be {est.currency}, the estimate's currency")
    a = ActualCost(
        org_id=p.org_id,
        option_id=o.id,
        total=body.total,
        currency=body.currency,
        estimate_total=est.total,
        rate_table=est.rate_table,
        note=body.note,
        recorded_by=p.user.id,
    )
    db.add(a)
    db.flush()
    audit(db, "option.actual_cost", p.org_id, p.user.id, str(o.id), total=body.total)
    db.commit()
    return _out(a)


@router.get("/options/{option_id}/actual-costs", response_model=list[ActualCostOut])
def list_actuals(
    option_id: uuid.UUID, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> list[ActualCostOut]:
    o, _, _ = _option(db, p, option_id)
    rows = db.scalars(select(ActualCost).where(ActualCost.option_id == o.id).order_by(ActualCost.at.desc()))
    return [_out(a) for a in rows]
