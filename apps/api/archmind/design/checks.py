"""Check engine (ARCH-151): rule pack + layout -> pass / fail / unknown per rule. Unknown is never pass."""

from typing import Literal

from pydantic import BaseModel

from archmind.design.brief import DesignBrief
from archmind.design.geometry import Rect
from archmind.design.layout import LayoutOption
from archmind.design.rules import RulePack

Result = Literal["pass", "fail", "unknown"]


class CheckItem(BaseModel):
    rule_id: str
    subject: str
    result: Result
    measured: float | None = None
    limit: float | None = None
    unit: str = ""
    rule_status: str = ""  # provisional | verified | internal


def _cmp(
    pack: RulePack, rule_id: str, subject: str, measured: float, kind: Literal["min", "max"], unit: str
) -> CheckItem:
    rule = pack.get(rule_id)
    if rule is None:
        return CheckItem(
            rule_id=rule_id, subject=subject, result="unknown", measured=round(measured, 3), unit=unit
        )
    ok = measured >= rule.value - 1e-6 if kind == "min" else measured <= rule.value + 1e-6
    return CheckItem(
        rule_id=rule_id,
        subject=subject,
        result="pass" if ok else "fail",
        measured=round(measured, 3),
        limit=rule.value,
        unit=unit,
        rule_status=rule.status,
    )


def _internal(rule_id: str, subject: str, ok: bool) -> CheckItem:
    return CheckItem(
        rule_id=rule_id, subject=subject, result="pass" if ok else "fail", rule_status="internal"
    )


def run_checks(opt: LayoutOption, brief: DesignBrief, pack: RulePack) -> list[CheckItem]:
    plot_area = opt.plot.area
    items = [
        _cmp(pack, "setback.front.min", "plot", brief.setbacks.front, "min", "m"),
        _cmp(pack, "setback.rear.min", "plot", brief.setbacks.rear, "min", "m"),
        _cmp(pack, "setback.side.min", "plot (left)", brief.setbacks.left, "min", "m"),
        _cmp(pack, "setback.side.min", "plot (right)", brief.setbacks.right, "min", "m"),
        _cmp(pack, "floors.max", "building", len(opt.floors), "max", "count"),
        _cmp(pack, "coverage.max", "building", opt.floors[0].footprint.area / plot_area, "max", "ratio"),
        _cmp(
            pack, "far.max", "building", sum(f.footprint.area for f in opt.floors) / plot_area, "max", "ratio"
        ),
    ]
    for f in opt.floors:
        label = f"floor {f.level}"
        items.append(_internal("footprint.inside_setbacks", label, _buildable(brief).contains(f.footprint)))
        if f.corridor is not None:
            items.append(
                _cmp(pack, "corridor.width.min", f"{label} corridor", f.corridor.min_side, "min", "m")
            )
        if f.stair is not None:
            items.append(_cmp(pack, "stair.width.min", f"{label} stair", f.stair.min_side, "min", "m"))
        parts = [r.rect for r in f.rooms] + [x for x in (f.corridor, f.stair) if x is not None]
        overlap = any(a.overlaps(b) for i, a in enumerate(parts) for b in parts[i + 1 :])
        items.append(_internal("rooms.no_overlap", label, not overlap))
        for r in f.rooms:
            items.append(_internal("room.inside_footprint", r.id, f.footprint.contains(r.rect)))
            items.append(_cmp(pack, f"room.{r.type}.area.min", r.id, r.rect.area, "min", "m2"))
            items.append(_cmp(pack, f"room.{r.type}.width.min", r.id, r.rect.min_side, "min", "m"))
    return items


def _buildable(brief: DesignBrief) -> Rect:
    return Rect(
        x=brief.setbacks.left,
        y=brief.setbacks.front,
        w=brief.buildable_width,
        d=brief.buildable_depth,
    )


def hard_failures(opt: LayoutOption, brief: DesignBrief, pack: RulePack) -> list[CheckItem]:
    """Failures of rules the generator itself controls. Brief-level failures (setbacks) are reported,
    not used to discard options, because no layout can fix them."""
    brief_level = {"setback.front.min", "setback.rear.min", "setback.side.min"}
    return [c for c in run_checks(opt, brief, pack) if c.result == "fail" and c.rule_id not in brief_level]
