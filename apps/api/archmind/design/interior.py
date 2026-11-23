"""Interior design of an option (ARCH-156): furniture, fixtures, decor, plants and finishes per room.

Positions are room-local metres from the room's front-left corner (front = road side, y = 0), item
centre, rotation in 90-degree steps. rot 0 puts the item's back towards the front wall (it faces +y);
90 faces -x; 180 faces -y; 270 faces +x. Fit checks are concept-level: rectangles, not real geometry.
"""

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from archmind.design.layout import LayoutOption, Room
from archmind.design.walls import STOREY_HEIGHT, openings

CATALOG = Path(__file__).parent / "interiors" / "catalog.json"
INSET = 0.06  # ponytail: half an internal wall; external walls are thicker, the check is concept-level
WALL_H = STOREY_HEIGHT - 0.15  # clear height below the slab
DOOR_H, WINDOW_H = 2.1, 1.2
Side = Literal["front", "rear", "left", "right"]
Rot = Literal[0, 90, 180, 270]
HEX = r"^#[0-9a-fA-F]{6}$"


class CatalogItem(BaseModel):
    id: str
    name: str
    category: Literal["furniture", "fixture", "decor", "plant"]
    kind: str
    rooms: list[str]
    w: float
    d: float
    h: float
    shape: str
    layer: Literal["floor", "rug", "wall", "top"]
    place: Literal["wall", "free", "corner", "top"]
    colour: str
    price: float
    styles: list[str]
    clear: float = 0.0
    elev: float = 0.0
    surface: bool = False
    seats: int = 0

    def allowed_in(self, room_type: str) -> bool:
        return "any" in self.rooms or room_type in self.rooms


class Finish(BaseModel):
    id: str
    name: str
    pattern: str
    colour: str
    rate_m2: float


class Theme(BaseModel):
    id: str
    name: str
    wall: str
    floor: str
    wet_wall: str
    wet_floor: str
    feature: str | None
    extras: dict[str, list[str]]


class Catalog(BaseModel):
    version: str
    status: str
    currency: str
    source: str
    items: list[CatalogItem]
    wall_finishes: list[Finish]
    floor_finishes: list[Finish]
    themes: list[Theme]
    room_kinds: dict[str, list[str]]

    def item(self, item_id: str) -> CatalogItem:
        return self._items[item_id]

    def model_post_init(self, _: object) -> None:
        self._items = {i.id: i for i in self.items}
        self._walls = {f.id: f for f in self.wall_finishes}
        self._floors = {f.id: f for f in self.floor_finishes}
        self._themes = {t.id: t for t in self.themes}

    def wall(self, fid: str) -> Finish:
        return self._walls[fid]

    def floor(self, fid: str) -> Finish:
        return self._floors[fid]

    def theme(self, tid: str) -> Theme:
        return self._themes[tid]

    def has(self, kind: Literal["item", "wall", "floor", "theme"], key: str) -> bool:
        table: dict[str, Mapping[str, object]] = {
            "item": self._items,
            "wall": self._walls,
            "floor": self._floors,
            "theme": self._themes,
        }
        return key in table[kind]


@cache
def catalog() -> Catalog:
    return Catalog.model_validate(json.loads(CATALOG.read_text()))


class Placement(BaseModel):
    uid: str = Field(min_length=1, max_length=40)
    item_id: str = Field(max_length=60)
    room_id: str = Field(max_length=40)
    x: float = Field(ge=-1, le=60)
    y: float = Field(ge=-1, le=60)
    rot: Rot = 0
    colour: str | None = Field(default=None, pattern=HEX)


class RoomFinish(BaseModel):
    wall: str = Field(max_length=60)
    wall_colour: str | None = Field(default=None, pattern=HEX)  # custom paint colour
    floor: str = Field(max_length=60)
    feature_side: Side | None = None
    feature: str | None = Field(default=None, max_length=60)


class Interior(BaseModel):
    theme: str = Field(max_length=40)
    rooms: dict[str, RoomFinish]
    items: list[Placement] = Field(max_length=400)

    @model_validator(mode="after")
    def _known_ids(self) -> "Interior":
        cat = catalog()
        if not cat.has("theme", self.theme):
            raise ValueError(f"unknown theme {self.theme!r}")
        for rf in self.rooms.values():
            if not cat.has("wall", rf.wall) or not cat.has("floor", rf.floor):
                raise ValueError("unknown wall or floor finish")
            if rf.feature is not None and not cat.has("wall", rf.feature):
                raise ValueError(f"unknown feature wall finish {rf.feature!r}")
        for p in self.items:
            if not cat.has("item", p.item_id):
                raise ValueError(f"unknown catalogue item {p.item_id!r}")
        if len({p.uid for p in self.items}) != len(self.items):
            raise ValueError("item uids must be unique")
        return self


class OpeningInfo(BaseModel):
    kind: Literal["door", "window"]
    side: Side
    offset: float  # centre along the wall from the room's left/front corner
    width: float


class RoomInfo(BaseModel):
    id: str
    name: str
    type: str
    floor: int
    x: float
    y: float
    w: float
    d: float
    openings: list[OpeningInfo]


class FitIssue(BaseModel):
    uid: str | None
    room_id: str
    rule: str
    result: Literal["warn", "fail"]
    message: str


class CostLine(BaseModel):
    group: str
    description: str
    qty: float
    unit: str
    rate: float
    amount: float


class InteriorCost(BaseModel):
    currency: str
    lines: list[CostLine]
    total: float
    label: str = "Indicative interiors estimate - not a quotation"
    warnings: list[str]


Box = tuple[float, float, float, float]  # x0, y0, x1, y1


def all_rooms(layout: LayoutOption) -> dict[str, Room]:
    return {r.id: r for f in layout.floors for r in f.rooms}


def room_info(layout: LayoutOption) -> list[RoomInfo]:
    out: list[RoomInfo] = []
    for f in layout.floors:
        ops = openings(f)
        for r in f.rooms:
            rc = r.rect
            infos = []
            for o in ops:
                side: Side
                if o.horizontal and abs(o.x - (rc.x + rc.w / 2)) <= rc.w / 2 and abs(o.y - rc.y) < 1e-6:
                    side, off = "front", o.x - rc.x
                elif (
                    o.horizontal
                    and abs(o.x - (rc.x + rc.w / 2)) <= rc.w / 2
                    and abs(o.y - rc.y - rc.d) < 1e-6
                ):
                    side, off = "rear", o.x - rc.x
                elif not o.horizontal and abs(o.y - (rc.y + rc.d / 2)) <= rc.d / 2 and abs(o.x - rc.x) < 1e-6:
                    side, off = "left", o.y - rc.y
                elif (
                    not o.horizontal
                    and abs(o.y - (rc.y + rc.d / 2)) <= rc.d / 2
                    and abs(o.x - rc.x - rc.w) < 1e-6
                ):
                    side, off = "right", o.y - rc.y
                else:
                    continue
                if o.room_id != r.id and o.kind == "window":
                    continue  # a neighbour's window on a shared line is not ours
                infos.append(OpeningInfo(kind=o.kind, side=side, offset=round(off, 3), width=o.width))
            out.append(
                RoomInfo(
                    id=r.id,
                    name=r.name,
                    type=r.type,
                    floor=r.floor,
                    x=rc.x,
                    y=rc.y,
                    w=rc.w,
                    d=rc.d,
                    openings=infos,
                )
            )
    return out


def size(item: CatalogItem, rot: int) -> tuple[float, float]:
    return (item.d, item.w) if rot in (90, 270) else (item.w, item.d)


def box(item: CatalogItem, x: float, y: float, rot: int) -> Box:
    sw, sd = size(item, rot)
    return (x - sw / 2, y - sd / 2, x + sw / 2, y + sd / 2)


def back_side(rot: int) -> Side:
    return {0: "front", 90: "right", 180: "rear", 270: "left"}[rot]  # type: ignore[return-value]


def front_zone(item: CatalogItem, b: Box, rot: int, depth: float) -> Box:
    x0, y0, x1, y1 = b
    return {
        0: (x0, y1, x1, y1 + depth),
        180: (x0, y0 - depth, x1, y0),
        90: (x0 - depth, y0, x0, y1),
        270: (x1, y0, x1 + depth, y1),
    }[rot]


def overlap(a: Box, b: Box, tol: float = 0.005) -> bool:
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def inside(b: Box, ri: RoomInfo, inset: float = INSET) -> bool:
    return (
        b[0] >= inset - 1e-6
        and b[1] >= inset - 1e-6
        and b[2] <= ri.w - inset + 1e-6
        and b[3] <= ri.d - inset + 1e-6
    )


def opening_zone(o: OpeningInfo, ri: RoomInfo, depth: float) -> Box:
    a, b = o.offset - o.width / 2, o.offset + o.width / 2
    return {
        "front": (a, 0.0, b, depth),
        "rear": (a, ri.d - depth, b, ri.d),
        "left": (0.0, a, depth, b),
        "right": (ri.w - depth, a, ri.w, b),
    }[o.side]


def _span(b: Box, side: Side) -> tuple[float, float]:
    return (b[0], b[2]) if side in ("front", "rear") else (b[1], b[3])


def _gap_to_wall(b: Box, side: Side, ri: RoomInfo) -> float:
    return {"front": b[1], "rear": ri.d - b[3], "left": b[0], "right": ri.w - b[2]}[side]


def item_issues(p: Placement, others: list[Placement], ri: RoomInfo, room_type: str) -> list[FitIssue]:
    """Fit problems for one placement against the room and the other placements in that room."""
    cat = catalog()
    it = cat.item(p.item_id)
    b = box(it, p.x, p.y, p.rot)
    out: list[FitIssue] = []

    def add(rule: str, result: Literal["warn", "fail"], msg: str) -> None:
        out.append(FitIssue(uid=p.uid, room_id=ri.id, rule=rule, result=result, message=f"{it.name}: {msg}"))

    if not it.allowed_in(room_type):
        add("item.room_type", "fail", f"not meant for a {room_type}")
    if not inside(b, ri):
        add("item.inside_room", "fail", "sticks out of the room")
    if it.layer == "wall":
        side = back_side(p.rot)
        if _gap_to_wall(b, side, ri) > 0.15 + INSET:
            add("item.on_wall", "fail", "must hang on a wall: move it against one")
        lo, hi = _span(b, side)
        for o in ri.openings:
            if o.side == side and lo < o.offset + o.width / 2 and o.offset - o.width / 2 < hi:
                add("item.over_opening", "fail", f"hangs over a {o.kind}")
        for q in others:
            qi = cat.item(q.item_id)
            if qi.layer == "wall" and overlap(b, box(qi, q.x, q.y, q.rot)) and back_side(q.rot) == side:
                add("item.overlap", "fail", f"overlaps {qi.name}")
        return out
    if it.layer == "top":
        if not any(
            cat.item(q.item_id).surface
            and _contains_point(box(cat.item(q.item_id), q.x, q.y, q.rot), p.x, p.y)
            for q in others
        ):
            add("item.on_surface", "warn", "is meant to stand on a table or unit")
        return out
    if it.layer == "rug":
        return out
    for o in ri.openings:
        if o.kind == "door" and overlap(b, opening_zone(o, ri, o.width)):
            add("item.door_clear", "fail", "blocks the door swing")
        if o.kind == "window" and it.h > 1.0 and overlap(b, opening_zone(o, ri, 0.3)):
            add("item.window_clear", "warn", "blocks a window")
    for q in others:
        qi = cat.item(q.item_id)
        if qi.layer == "floor" and overlap(b, box(qi, q.x, q.y, q.rot)):
            add("item.overlap", "fail", f"overlaps {qi.name}")
    if it.clear > 0:
        z = front_zone(it, b, p.rot, it.clear)
        blocked = not inside(z, ri) or any(
            cat.item(q.item_id).layer == "floor" and overlap(z, box(cat.item(q.item_id), q.x, q.y, q.rot))
            for q in others
        )
        if blocked:
            add("item.front_clearance", "warn", f"needs {it.clear:.2f} m clear in front")
    return out


def _contains_point(b: Box, x: float, y: float) -> bool:
    return b[0] <= x <= b[2] and b[1] <= y <= b[3]


def fit_issues(layout: LayoutOption, interior: Interior) -> list[FitIssue]:
    infos = {ri.id: ri for ri in room_info(layout)}
    out: list[FitIssue] = []
    for p in interior.items:
        ri = infos.get(p.room_id)
        if ri is None:
            out.append(
                FitIssue(
                    uid=p.uid, room_id=p.room_id, rule="item.room", result="fail", message="no such room"
                )
            )
            continue
        others = [q for q in interior.items if q.room_id == p.room_id and q.uid != p.uid]
        out += item_issues(p, others, ri, ri.type)
    return out


def _wall_areas(ri: RoomInfo) -> dict[Side, float]:
    lengths: dict[Side, float] = {"front": ri.w, "rear": ri.w, "left": ri.d, "right": ri.d}
    areas = {s: v * WALL_H for s, v in lengths.items()}
    for o in ri.openings:
        areas[o.side] -= o.width * (DOOR_H if o.kind == "door" else WINDOW_H)
    return {s: max(a, 0.0) for s, a in areas.items()}


def cost(layout: LayoutOption, interior: Interior) -> InteriorCost:
    cat = catalog()
    infos = {ri.id: ri for ri in room_info(layout)}
    lines: list[CostLine] = []
    groups = {"furniture": "Furniture", "fixture": "Fixtures", "decor": "Decor", "plant": "Plants"}
    counts: dict[str, int] = {}
    for p in interior.items:
        counts[p.item_id] = counts.get(p.item_id, 0) + 1
    for item_id, n in sorted(counts.items(), key=lambda kv: (cat.item(kv[0]).category, kv[0])):
        it = cat.item(item_id)
        lines.append(
            CostLine(
                group=groups[it.category],
                description=it.name,
                qty=n,
                unit="no",
                rate=it.price,
                amount=n * it.price,
            )
        )
    wall_m2: dict[str, float] = {}
    floor_m2: dict[str, float] = {}
    for rid, rf in interior.rooms.items():
        ri = infos.get(rid)
        if ri is None:
            continue
        for side, a in _wall_areas(ri).items():
            fid = rf.feature if rf.feature and rf.feature_side == side else rf.wall
            wall_m2[fid] = wall_m2.get(fid, 0.0) + a
        floor_m2[rf.floor] = floor_m2.get(rf.floor, 0.0) + ri.w * ri.d
    for fid, a in sorted(wall_m2.items()):
        f = cat.wall(fid)
        lines.append(
            CostLine(
                group="Wall finishes",
                description=f.name,
                qty=round(a, 2),
                unit="m2",
                rate=f.rate_m2,
                amount=round(a * f.rate_m2, 2),
            )
        )
    for fid, a in sorted(floor_m2.items()):
        f = cat.floor(fid)
        lines.append(
            CostLine(
                group="Floor finishes",
                description=f.name,
                qty=round(a, 2),
                unit="m2",
                rate=f.rate_m2,
                amount=round(a * f.rate_m2, 2),
            )
        )
    warnings = [
        f"prices are {cat.status}: {cat.source}",
        "wall areas: room perimeter x clear height less door and window openings",
    ]
    return InteriorCost(
        currency=cat.currency, lines=lines, total=round(sum(x.amount for x in lines), 2), warnings=warnings
    )
