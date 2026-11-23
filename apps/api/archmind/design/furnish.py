"""Auto-furnish a layout in a design theme (ARCH-157). Deterministic: same layout + theme -> same interior.

Each room type has a list of essential kinds (bed, wardrobe, ...) plus theme extras (plants, decor).
For each, the best catalogue item that fits is placed at the first candidate position, nearest a
target point, that passes the hard fit rules (inside, no overlap, door swing) and front clearance.
"""

import math

from archmind.design.interior import (
    Box,
    CatalogItem,
    Interior,
    OpeningInfo,
    Placement,
    RoomFinish,
    RoomInfo,
    Rot,
    Side,
    box,
    catalog,
    item_issues,
    room_info,
)
from archmind.design.layout import LayoutOption

STEP = 0.05
WET = {"bathroom", "kitchen"}
ROT_FOR_WALL: dict[Side, Rot] = {"front": 0, "rear": 180, "left": 270, "right": 90}


def _wall_spots(it: CatalogItem, ri: RoomInfo, inset: float = 0.06) -> list[tuple[float, float, Rot]]:
    out: list[tuple[float, float, Rot]] = []
    for side, rot in ROT_FOR_WALL.items():
        sw, sd = (it.d, it.w) if rot in (90, 270) else (it.w, it.d)
        along = sw if side in ("front", "rear") else sd
        length = ri.w if side in ("front", "rear") else ri.d
        n = int((length - 2 * inset - along) / STEP)
        for i in range(max(n + 1, 0)):
            c = inset + along / 2 + i * STEP
            x, y = {
                "front": (c, inset + sd / 2),
                "rear": (c, ri.d - inset - sd / 2),
                "left": (inset + sw / 2, c),
                "right": (ri.w - inset - sw / 2, c),
            }[side]
            out.append((round(x, 3), round(y, 3), rot))
    return out


def _free_spots(it: CatalogItem, ri: RoomInfo) -> list[tuple[float, float, Rot]]:
    out: list[tuple[float, float, Rot]] = []
    rots: tuple[Rot, Rot] = (0, 90)
    for rot in rots:
        sw, sd = (it.d, it.w) if rot == 90 else (it.w, it.d)
        nx, ny = int((ri.w - sw) / (2 * STEP)), int((ri.d - sd) / (2 * STEP))
        for i in range(max(nx + 1, 0)):
            for j in range(max(ny + 1, 0)):
                out.append((round(sw / 2 + i * 2 * STEP, 3), round(sd / 2 + j * 2 * STEP, 3), rot))
    return out


def _centre(b: Box) -> tuple[float, float]:
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _target(
    kind: str, it: CatalogItem, ri: RoomInfo, placed: dict[str, tuple[CatalogItem, Placement]]
) -> tuple[float, float]:
    cx, cy = ri.w / 2, ri.d / 2
    corners = [(0.0, 0.0), (ri.w, 0.0), (0.0, ri.d), (ri.w, ri.d)]
    if kind in ("coffee_table", "rug", "armchair") and "sofa" in placed:
        si, sp = placed["sofa"]
        sx, sy = sp.x, sp.y
        fx, fy = {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}[sp.rot]
        reach = (si.d / 2 + 0.45 + it.d / 2) if kind != "armchair" else (si.d / 2 + 1.2)
        return (sx + fx * reach, sy + fy * reach)
    if kind == "tv_unit" and "sofa" in placed:
        sp = placed["sofa"][1]
        return (ri.w - sp.x, ri.d - sp.y)
    if kind == "side_table" and "bed" in placed:
        bi, bp = placed["bed"]
        x0, y0, x1, y1 = box(bi, bp.x, bp.y, bp.rot)
        return (x0 - 0.3, y0) if bp.rot in (0, 180) else (x0, y0 - 0.3)
    if kind == "fridge" and "counter" in placed:
        ci, cp = placed["counter"]
        x0, y0, _, _ = box(ci, cp.x, cp.y, cp.rot)
        return (x0, y0)
    if kind == "rug" and "bed" in placed:
        return (placed["bed"][1].x, placed["bed"][1].y)
    if it.place == "corner" or kind in ("wardrobe", "shower", "wc"):
        # furthest corner from the room's doors keeps clutter out of the way in
        doors = [o for o in ri.openings if o.kind == "door"]

        def door_dist(c: tuple[float, float]) -> float:
            if not doors:
                return 0.0
            pts = [_door_point(o, ri) for o in doors]
            return min(math.dist(c, p) for p in pts)

        return max(corners, key=door_dist)
    return (cx, cy)


def _door_point(o: OpeningInfo, ri: RoomInfo) -> tuple[float, float]:
    off = o.offset
    return {"front": (off, 0.0), "rear": (off, ri.d), "left": (0.0, off), "right": (ri.w, off)}[o.side]


def _door_walls(ri: RoomInfo) -> set[str]:
    return {o.side for o in ri.openings if o.kind == "door"}


def _try_place(
    it: CatalogItem,
    kind: str,
    ri: RoomInfo,
    items: list[Placement],
    placed: dict[str, tuple[CatalogItem, Placement]],
    uid: str,
    strict: bool,
) -> Placement | None:
    if it.layer == "top":
        hosts = [p for p in items if p.room_id == ri.id and catalog().item(p.item_id).surface]
        taken = {(p.x, p.y) for p in items if catalog().item(p.item_id).layer == "top"}
        for h in hosts:
            spot = (h.x, h.y)
            if spot not in taken:
                return Placement(uid=uid, item_id=it.id, room_id=ri.id, x=h.x, y=h.y, rot=h.rot)
        return None
    spots = _free_spots(it, ri) if it.place == "free" else _wall_spots(it, ri)
    tx, ty = _target(kind, it, ri, placed)
    door_walls = _door_walls(ri)
    rot_for = {v: k for k, v in ROT_FOR_WALL.items()}

    def score(s: tuple[float, float, Rot]) -> float:
        penalty = (
            3.0
            if it.place != "free" and rot_for[s[2]] in door_walls and kind in ("bed", "sofa", "counter")
            else 0.0
        )
        return math.dist((s[0], s[1]), (tx, ty)) + penalty

    others = [p for p in items if p.room_id == ri.id]
    before = {q.uid: len(item_issues(q, [o for o in others if o.uid != q.uid], ri, ri.type)) for q in others}

    def harms_others(p: Placement) -> bool:
        # strict pass: the new item must not take the clearance an earlier item needs
        return any(
            len(item_issues(q, [o for o in others if o.uid != q.uid] + [p], ri, ri.type)) > before[q.uid]
            for q in others
        )

    for x, y, rot in sorted(spots, key=score):
        p = Placement(uid=uid, item_id=it.id, room_id=ri.id, x=x, y=y, rot=rot)
        issues = item_issues(p, others, ri, ri.type)
        if any(i.result == "fail" for i in issues):
            continue
        if not strict or (not issues and not harms_others(p)):
            return p
    return None


def _candidates(kind: str, room_type: str, theme_styles: str) -> list[CatalogItem]:
    items = [i for i in catalog().items if i.kind == kind and i.allowed_in(room_type)]
    # theme match first, then larger items first (fall back to smaller ones if they do not fit)
    return sorted(items, key=lambda i: (theme_styles not in i.styles, -(i.w * i.d)))


def furnish(layout: LayoutOption, theme_id: str = "modern") -> Interior:
    cat = catalog()
    theme = cat.theme(theme_id)
    items: list[Placement] = []
    rooms: dict[str, RoomFinish] = {}
    for ri in room_info(layout):
        wet = ri.type in WET
        rooms[ri.id] = RoomFinish(
            wall=theme.wet_wall if ri.type == "bathroom" else theme.wall,
            floor=theme.wet_floor if wet else theme.floor,
            feature_side=None,
            feature=None,
        )
        if theme.feature and ri.type in ("living", "bedroom"):
            # feature wall behind the bed / sofa is decided after placement
            rooms[ri.id].feature = theme.feature
        placed: dict[str, tuple[CatalogItem, Placement]] = {}
        wanted: list[tuple[str, str | None]] = [(k, None) for k in cat.room_kinds.get(ri.type, [])]
        wanted += [(cat.item(x).kind, x) for x in theme.extras.get(ri.type, [])]
        for n, (kind, exact) in enumerate(wanted):
            options = [cat.item(exact)] if exact else _candidates(kind, ri.type, theme.id)
            # every variant gets a clean try (no warnings) before any variant is accepted with warnings
            for strict in (True, False):
                p = next(
                    (
                        q
                        for it in options
                        if (q := _try_place(it, kind, ri, items, placed, f"{ri.id}-{n}", strict))
                    ),
                    None,
                )
                if p is not None:
                    items.append(p)
                    placed.setdefault(kind, (cat.item(p.item_id), p))
                    break
        anchor = placed.get("bed") or placed.get("sofa")
        if rooms[ri.id].feature and anchor:
            rooms[ri.id].feature_side = {0: "front", 90: "right", 180: "rear", 270: "left"}[anchor[1].rot]  # type: ignore[assignment]
        elif rooms[ri.id].feature:
            rooms[ri.id].feature = None
    return Interior(theme=theme.id, rooms=rooms, items=items)
