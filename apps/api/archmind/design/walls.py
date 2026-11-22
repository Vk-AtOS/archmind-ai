"""Walls and openings derived from a layout. One source for drawings, quantities and IFC so they agree.

Centreline model: walls run along room/corridor/stair edges; rooms keep their centreline areas.
"""

from typing import Literal

from pydantic import BaseModel

from archmind.design.layout import Floor

EXT_THICKNESS = 0.23  # ponytail: one-brick external wall; make a rule-pack/spec value per market
INT_THICKNESS = 0.115  # half-brick partition
STOREY_HEIGHT = 3.0
DOOR_W = {"bathroom": 0.75}
DOOR_W_DEFAULT = 0.9
ENTRANCE_W = 1.0
WINDOW_W = {"bathroom": 0.6}
WINDOW_W_DEFAULT = 1.2


class Wall(BaseModel):
    id: str
    floor: int
    x1: float
    y1: float
    x2: float
    y2: float
    external: bool

    @property
    def length(self) -> float:
        return abs(self.x2 - self.x1) + abs(self.y2 - self.y1)

    @property
    def thickness(self) -> float:
        return EXT_THICKNESS if self.external else INT_THICKNESS


class Opening(BaseModel):
    id: str
    floor: int
    kind: Literal["door", "window"]
    room_id: str
    x: float  # centre point on the wall line
    y: float
    width: float
    horizontal: bool  # wall runs along x


def _union(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def walls(floor: Floor) -> list[Wall]:
    fp = floor.footprint
    rects = [r.rect for r in floor.rooms] + [x for x in (floor.corridor, floor.stair) if x is not None]
    lines: dict[tuple[str, float], list[tuple[float, float]]] = {}
    for r in rects + [fp]:
        for y in (r.y, r.y + r.d):
            lines.setdefault(("h", round(y, 2)), []).append((round(r.x, 2), round(r.x + r.w, 2)))
        for x in (r.x, r.x + r.w):
            lines.setdefault(("v", round(x, 2)), []).append((round(r.y, 2), round(r.y + r.d, 2)))
    out: list[Wall] = []
    for (axis, c), spans in sorted(lines.items()):
        for a, b in _union(spans):
            if b - a < 1e-6:
                continue
            ext = (
                axis == "h"
                and (abs(c - fp.y) < 1e-6 or abs(c - (fp.y + fp.d)) < 1e-6)
                or axis == "v"
                and (abs(c - fp.x) < 1e-6 or abs(c - (fp.x + fp.w)) < 1e-6)
            )
            x1, y1, x2, y2 = (a, c, b, c) if axis == "h" else (c, a, c, b)
            out.append(
                Wall(
                    id=f"F{floor.level}-W{len(out) + 1}",
                    floor=floor.level,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    external=ext,
                )
            )
    return out


def openings(floor: Floor) -> list[Opening]:
    fp = floor.footprint
    out: list[Opening] = []
    for r in floor.rooms:
        rc = r.rect
        cx, cy = rc.x + rc.w / 2, rc.y + rc.d / 2
        if r.door_side is not None:
            y = rc.y + rc.d if r.door_side == "rear" else rc.y
            w = DOOR_W.get(r.type, DOOR_W_DEFAULT)
            out.append(
                Opening(
                    id=f"{r.id}-D",
                    floor=r.floor,
                    kind="door",
                    room_id=r.id,
                    x=cx,
                    y=y,
                    width=w,
                    horizontal=True,
                )
            )
        # One window per external edge, entrance door on the front edge of the ground-floor living room.
        edges = [
            ("front", abs(rc.y - fp.y) < 1e-6, cx, rc.y, True, rc.w),
            ("rear", abs(rc.y + rc.d - fp.y - fp.d) < 1e-6, cx, rc.y + rc.d, True, rc.w),
            ("left", abs(rc.x - fp.x) < 1e-6, rc.x, cy, False, rc.d),
            ("right", abs(rc.x + rc.w - fp.x - fp.w) < 1e-6, rc.x + rc.w, cy, False, rc.d),
        ]
        for side, on_edge, x, y, horiz, span in edges:
            if not on_edge:
                continue
            if r.type == "living" and r.floor == 0 and side == "front":
                out.append(
                    Opening(
                        id=f"{r.id}-ENT",
                        floor=r.floor,
                        kind="door",
                        room_id=r.id,
                        x=x - span / 4,
                        y=y,
                        width=ENTRANCE_W,
                        horizontal=horiz,
                    )
                )
                out.append(
                    Opening(
                        id=f"{r.id}-W{side}",
                        floor=r.floor,
                        kind="window",
                        room_id=r.id,
                        x=x + span / 4,
                        y=y,
                        width=WINDOW_W_DEFAULT,
                        horizontal=horiz,
                    )
                )
                continue
            w = min(WINDOW_W.get(r.type, WINDOW_W_DEFAULT), span - 0.4)
            if w > 0.3:
                out.append(
                    Opening(
                        id=f"{r.id}-W{side}",
                        floor=r.floor,
                        kind="window",
                        room_id=r.id,
                        x=x,
                        y=y,
                        width=round(w, 2),
                        horizontal=horiz,
                    )
                )
    return out
