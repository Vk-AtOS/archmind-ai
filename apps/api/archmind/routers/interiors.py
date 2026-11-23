"""Interior studio API (ARCH-156): catalogue, auto-furnish by theme, edit, fit checks and cost."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from archmind.db import get_db, utcnow
from archmind.design.furnish import furnish
from archmind.design.interior import (
    Catalog,
    FitIssue,
    Interior,
    InteriorCost,
    RoomInfo,
    all_rooms,
    catalog,
    cost,
    fit_issues,
    room_info,
)
from archmind.design.layout import LayoutOption
from archmind.models import OptionInterior
from archmind.routers.projects import _option
from archmind.security import Principal, audit, current

router = APIRouter(prefix="/api/v1", tags=["interiors"])
DEFAULT_THEME = "modern"


class InteriorOut(BaseModel):
    option_id: uuid.UUID
    saved: bool
    revision: int
    catalog_version: str
    interior: Interior
    rooms: list[RoomInfo]
    issues: list[FitIssue]
    cost: InteriorCost
    can_edit: bool


class InteriorIn(BaseModel):
    interior: Interior
    base_revision: int = Field(ge=0)  # 0 = first save


class ThemeIn(BaseModel):
    theme: str = Field(max_length=40)


def _out(
    o_id: uuid.UUID, layout: LayoutOption, it: Interior, row: OptionInterior | None, p: Principal
) -> InteriorOut:
    return InteriorOut(
        option_id=o_id,
        saved=row is not None,
        revision=row.revision if row else 0,
        catalog_version=catalog().version,
        interior=it,
        rooms=room_info(layout),
        issues=fit_issues(layout, it),
        cost=cost(layout, it),
        can_edit=p.can("design_interior"),
    )


def _check_rooms(layout: LayoutOption, it: Interior) -> None:
    rooms = all_rooms(layout)
    unknown = {p.room_id for p in it.items} | set(it.rooms)
    if unknown - rooms.keys():
        raise HTTPException(422, f"unknown room ids: {sorted(unknown - rooms.keys())}")


@router.get("/interiors/catalog", response_model=Catalog)
def get_catalog(_: Principal = Depends(current)) -> Catalog:
    return catalog()


@router.get("/options/{option_id}/interior", response_model=InteriorOut)
def get_interior(
    option_id: uuid.UUID, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> InteriorOut:
    """The saved interior, or an unsaved auto-furnished one in the default theme."""
    o, layout, _ = _option(db, p, option_id)
    row = db.get(OptionInterior, o.id)
    it = Interior.model_validate(row.data) if row else furnish(layout, DEFAULT_THEME)
    return _out(o.id, layout, it, row, p)


@router.post("/options/{option_id}/interior/auto", response_model=InteriorOut)
def auto_interior(
    option_id: uuid.UUID, body: ThemeIn, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> InteriorOut:
    """Auto-furnish the whole house in a theme. Not saved until the caller saves it."""
    o, layout, _ = _option(db, p, option_id)
    if not catalog().has("theme", body.theme):
        raise HTTPException(422, f"unknown theme {body.theme!r}")
    return _out(o.id, layout, furnish(layout, body.theme), db.get(OptionInterior, o.id), p)


@router.post("/options/{option_id}/interior/check", response_model=InteriorOut)
def check_interior(
    option_id: uuid.UUID, body: InteriorIn, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> InteriorOut:
    """Fit checks and cost for an edited interior, without saving (the editor calls this as you work)."""
    o, layout, _ = _option(db, p, option_id)
    _check_rooms(layout, body.interior)
    return _out(o.id, layout, body.interior, db.get(OptionInterior, o.id), p)


@router.put("/options/{option_id}/interior", response_model=InteriorOut)
def save_interior(
    option_id: uuid.UUID, body: InteriorIn, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> InteriorOut:
    p.require("design_interior")
    o, layout, _ = _option(db, p, option_id)
    _check_rooms(layout, body.interior)
    row = db.get(OptionInterior, o.id)
    current_rev = row.revision if row else 0
    if body.base_revision != current_rev:
        raise HTTPException(
            409, "someone else saved this interior since you opened it; reload to see their changes"
        )
    data = body.interior.model_dump(mode="json")
    if row is None:
        row = OptionInterior(
            option_id=o.id,
            org_id=p.org_id,
            data=data,
            catalog_version=catalog().version,
            updated_by=p.user.id,
        )
        db.add(row)
    else:
        row.data, row.revision, row.updated_by, row.updated_at = data, row.revision + 1, p.user.id, utcnow()
        row.catalog_version = catalog().version
    audit(db, "option.interior_save", p.org_id, p.user.id, str(o.id), items=len(body.interior.items))
    db.commit()
    return _out(o.id, layout, body.interior, row, p)
