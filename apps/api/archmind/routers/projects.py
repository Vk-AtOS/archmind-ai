import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from archmind.db import get_db
from archmind.design.brief import DesignBrief
from archmind.design.checks import CheckItem, run_checks
from archmind.design.drawings import ScheduleRow, plan_svg, schedule
from archmind.design.estimate import Estimate, estimate, load_rates
from archmind.design.ifc import build
from archmind.design.layout import LayoutOption, generate
from archmind.design.quantities import Quantities, compute
from archmind.design.rules import load_pack
from archmind.models import Brief, DesignOption, Project
from archmind.security import Principal, audit, current

router = APIRouter(prefix="/api/v1", tags=["projects"])
RATE_TABLE = "sample-inr-v0"  # ponytail: per-project rate table once real tables exist (ARCH-153)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=300)


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    location: str
    rule_pack: str
    created_at: str


class OptionSummary(BaseModel):
    id: uuid.UUID
    label: str
    score: float
    failed_checks: int
    unknown_checks: int
    built_up_m2: float
    estimate_total: float
    currency: str


class BriefOut(BaseModel):
    id: uuid.UUID
    created_at: str
    data: dict[str, Any]
    options: list[OptionSummary]


class OptionDetail(BaseModel):
    id: uuid.UUID
    label: str
    layout: LayoutOption
    checks: list[CheckItem]
    quantities: Quantities
    estimate: Estimate
    schedule: list[ScheduleRow]


def _project(db: Session, p: Principal, project_id: uuid.UUID) -> Project:
    pr = db.get(Project, project_id)
    if pr is None or pr.org_id != p.org_id:  # same 404 for missing and other tenants: no existence leak
        raise HTTPException(404, "project not found")
    return pr


def _option(
    db: Session, p: Principal, option_id: uuid.UUID
) -> tuple[DesignOption, LayoutOption, DesignBrief]:
    o = db.get(DesignOption, option_id)
    if o is None or o.org_id != p.org_id:
        raise HTTPException(404, "option not found")
    b = db.get(Brief, o.brief_id)
    assert b is not None
    return o, LayoutOption.model_validate(o.layout), DesignBrief.model_validate(b.data)


def _summary(o: DesignOption, layout: LayoutOption, brief: DesignBrief) -> OptionSummary:
    checks = run_checks(layout, brief, load_pack(brief.rule_pack))
    q = compute(layout)
    est = estimate(q, load_rates(RATE_TABLE))
    return OptionSummary(
        id=o.id,
        label=o.label,
        score=o.score,
        failed_checks=sum(c.result == "fail" for c in checks),
        unknown_checks=sum(c.result == "unknown" for c in checks),
        built_up_m2=q.get("built_up_area").qty,
        estimate_total=est.total,
        currency=est.currency,
    )


def _out(pr: Project) -> ProjectOut:
    return ProjectOut(
        id=pr.id,
        name=pr.name,
        location=pr.location,
        rule_pack=pr.rule_pack,
        created_at=pr.created_at.isoformat(),
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(p: Principal = Depends(current), db: Session = Depends(get_db)) -> list[ProjectOut]:
    rows = db.scalars(select(Project).where(Project.org_id == p.org_id).order_by(Project.created_at.desc()))
    return [_out(r) for r in rows]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectIn, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> ProjectOut:
    p.require("create_project")
    pr = Project(org_id=p.org_id, name=body.name, location=body.location, created_by=p.user.id)
    db.add(pr)
    db.flush()
    audit(db, "project.create", p.org_id, p.user.id, str(pr.id))
    db.commit()
    return _out(pr)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> ProjectOut:
    return _out(_project(db, p, project_id))


@router.post("/projects/{project_id}/briefs", response_model=BriefOut, status_code=201)
def create_brief(
    project_id: uuid.UUID,
    body: dict[str, Any],
    p: Principal = Depends(current),
    db: Session = Depends(get_db),
) -> BriefOut:
    p.require("create_brief")
    pr = _project(db, p, project_id)
    try:
        brief = DesignBrief.model_validate({**body, "rule_pack": pr.rule_pack})
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from e
    layouts = generate(brief, n=3)
    if not layouts:
        raise HTTPException(
            422, "no layout satisfies the rules for this brief; enlarge the plot or reduce rooms"
        )
    b = Brief(org_id=p.org_id, project_id=pr.id, data=brief.model_dump(), created_by=p.user.id)
    db.add(b)
    db.flush()
    rows = []
    for lo in layouts:
        o = DesignOption(
            org_id=p.org_id,
            brief_id=b.id,
            label=lo.id,
            layout=lo.model_dump(mode="json"),
            score=lo.score.total if lo.score else 0.0,
            generator_version=lo.generator_version,
        )
        db.add(o)
        rows.append((o, lo))
    db.flush()
    audit(db, "brief.create", p.org_id, p.user.id, str(b.id), options=len(rows))
    db.commit()
    return BriefOut(
        id=b.id,
        created_at=b.created_at.isoformat(),
        data=b.data,
        options=[_summary(o, lo, brief) for o, lo in rows],
    )


@router.get("/projects/{project_id}/briefs", response_model=list[BriefOut])
def list_briefs(
    project_id: uuid.UUID, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> list[BriefOut]:
    pr = _project(db, p, project_id)
    out = []
    for b in db.scalars(select(Brief).where(Brief.project_id == pr.id).order_by(Brief.created_at.desc())):
        brief = DesignBrief.model_validate(b.data)
        opts = db.scalars(
            select(DesignOption).where(DesignOption.brief_id == b.id).order_by(DesignOption.label)
        )
        summaries = [_summary(o, LayoutOption.model_validate(o.layout), brief) for o in opts]
        out.append(BriefOut(id=b.id, created_at=b.created_at.isoformat(), data=b.data, options=summaries))
    return out


@router.get("/options/{option_id}", response_model=OptionDetail)
def get_option(
    option_id: uuid.UUID, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> OptionDetail:
    o, layout, brief = _option(db, p, option_id)
    q = compute(layout)
    return OptionDetail(
        id=o.id,
        label=o.label,
        layout=layout,
        checks=run_checks(layout, brief, load_pack(brief.rule_pack)),
        quantities=q,
        estimate=estimate(q, load_rates(RATE_TABLE)),
        schedule=schedule(layout),
    )


@router.get("/options/{option_id}/plans/{level}.svg")
def option_plan(
    option_id: uuid.UUID, level: int, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> Response:
    _, layout, _ = _option(db, p, option_id)
    if not 0 <= level < len(layout.floors):
        raise HTTPException(404, "no such floor")
    return Response(plan_svg(layout, level), media_type="image/svg+xml")


@router.get("/options/{option_id}/model.ifc")
def option_ifc(
    option_id: uuid.UUID, p: Principal = Depends(current), db: Session = Depends(get_db)
) -> Response:
    _, layout, _ = _option(db, p, option_id)
    audit(db, "option.export_ifc", p.org_id, p.user.id, str(option_id))
    db.commit()
    headers = {"Content-Disposition": f'attachment; filename="archmind-{layout.id}.ifc"'}
    return Response(build(layout).to_string(), media_type="application/x-step", headers=headers)
