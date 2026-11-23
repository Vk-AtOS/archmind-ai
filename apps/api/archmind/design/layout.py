"""Constraint-based layout generator (ARCH-148). Deterministic: same brief + seed -> same options.

Each floor is a footprint rectangle split into a front band, a corridor and a rear band. Rooms fill
each band left to right with widths proportional to their target areas. Candidates that fail any hard
rule (check engine) are discarded; the rest are scored on soft goals.
"""

import math
import random
from typing import Literal

from pydantic import BaseModel

from archmind.design.brief import DEFAULT_AREA, DesignBrief
from archmind.design.geometry import Rect
from archmind.design.rules import RulePack, load_pack

GENERATOR_VERSION = "0.3.1"
STAIR_W = 1.2
STAIR_D = 3.0
Side = Literal["front", "rear"]


class Room(BaseModel):
    id: str
    type: str
    name: str
    floor: int
    rect: Rect
    target_area_m2: float
    door_side: Side | None = None  # side facing the corridor


class Floor(BaseModel):
    level: int
    footprint: Rect
    corridor: Rect | None
    stair: Rect | None
    rooms: list[Room]


class Score(BaseModel):
    total: float
    adjacency: float
    living_at_front: float
    area_match: float
    efficiency: float


class LayoutOption(BaseModel):
    id: str
    seed: int
    generator_version: str = GENERATOR_VERSION
    rule_pack: str
    plot: Rect
    floors: list[Floor]
    score: Score | None = None


MIN_FOOTPRINT_DEPTH = 7.0  # two bands of ~3 m plus a corridor
TARGET_DEPTH = 8.0  # preferred depth: bands of ~3.5 m
NET_RATIO = 0.82  # ponytail: rooms vs gross floor area; tune from partner-rated layouts (ARCH-155)


def _footprint(
    brief: DesignBrief,
    pack: RulePack,
    per_floor: list[list[tuple[str, str, float]]],
    target_depth: float = TARGET_DEPTH,
) -> Rect:
    """Footprint sized to the largest floor's room programme: width first (so wide plots do not
    stretch rooms), then depth, capped by setbacks, coverage and floor-area ratio."""
    # Room coordinates are on a 1 cm grid, so the footprint origin snaps up to it (a 3.003 m setback,
    # e.g. 9.85 ft, starts the house at 3.01 m) and the usable size shrinks by the same amount.
    # Without this, rooms sat up to 5 mm outside the footprint and every candidate was rejected.
    x0 = math.ceil(brief.setbacks.left * 100 - 1e-9) / 100
    y0 = math.ceil(brief.setbacks.front * 100 - 1e-9) / 100
    bw = math.floor((brief.buildable_width - (x0 - brief.setbacks.left)) * 100 + 1e-9) / 100
    bd = math.floor((brief.buildable_depth - (y0 - brief.setbacks.front)) * 100 + 1e-9) / 100
    plot_area = brief.plot_width_m * brief.plot_depth_m
    stair = STAIR_W * STAIR_D if brief.floors > 1 else 0.0
    need = max(sum(r[2] for r in rooms) for rooms in per_floor) / NET_RATIO + stair
    max_fp = min(
        bw * bd,
        pack.value("coverage.max", 1.0) * plot_area,
        pack.value("far.max", 99.0) * plot_area / brief.floors,
    )
    width = min(bw, need / target_depth)
    depth = min(max(need / width, MIN_FOOTPRINT_DEPTH), max_fp / width, bd)
    return Rect(x=x0, y=y0, w=min(round(width, 2), bw), d=min(round(depth, 2), bd))


def _room_list(brief: DesignBrief) -> list[tuple[str, str, float]]:
    """(type, name, target area) for every requested room, numbered by type."""
    out: list[tuple[str, str, float]] = []
    for req in brief.rooms:
        for i in range(req.count):
            name = req.type.capitalize() + (f" {i + 1}" if req.count > 1 else "")
            out.append((req.type, name, req.target_area_m2 or DEFAULT_AREA[req.type]))
    return out


def _split_floors(rooms: list[tuple[str, str, float]], floors: int) -> list[list[tuple[str, str, float]]]:
    if floors == 1:
        return [rooms]
    social = {"living", "dining", "kitchen"}
    ground = [r for r in rooms if r[0] in social]
    upper = [r for r in rooms if r[0] == "bedroom"]
    baths = [r for r in rooms if r[0] == "bathroom"]
    ground.append(baths[0])  # one bathroom on the ground floor
    upper.extend(baths[1:])
    if not upper:  # nothing to put upstairs: keep a single usable floor plus stair landing
        upper, ground = ground[len(ground) // 2 :], ground[: len(ground) // 2]
    return [ground, upper]


WET_MIN_W = 1.5


def _room(level: int, rtype: str, name: str, target: float, rect: Rect, door: Side | None) -> Room:
    return Room(
        id=f"F{level}-{name.replace(' ', '')}",
        type=rtype,
        name=name,
        floor=level,
        rect=rect,
        target_area_m2=target,
        door_side=door,
    )


def _fill_band(band: Rect, rooms: list[tuple[str, str, float]], level: int, door: Side | None) -> list[Room]:
    """Bathrooms share one stacked column (a wet wall); other rooms split the rest of the band
    width in proportion to their target areas."""
    wet = [r for r in rooms if r[0] == "bathroom"]
    dry = [r for r in rooms if r[0] != "bathroom"]
    out: list[Room] = []
    x = band.x
    if wet:
        col_w = round(max(WET_MIN_W, sum(r[2] for r in wet) / band.d), 2)
        col_w = band.w if not dry else min(col_w, band.w)
        each_d = round(band.d / len(wet), 2)
        for i, (rtype, name, target) in enumerate(wet):
            d = round(band.d - each_d * i, 2) if i == len(wet) - 1 else each_d
            out.append(
                _room(
                    level, rtype, name, target, Rect(x=x, y=round(band.y + each_d * i, 2), w=col_w, d=d), door
                )
            )
        x = round(x + col_w, 2)
    total = sum(r[2] for r in dry)
    rest_w = band.x + band.w - x
    for i, (rtype, name, target) in enumerate(dry):
        w = band.x + band.w - x if i == len(dry) - 1 else round(rest_w * target / total, 2)
        out.append(
            _room(level, rtype, name, target, Rect(x=round(x, 2), y=band.y, w=round(w, 2), d=band.d), door)
        )
        x += w
    return out


def _keep_together(band: list[tuple[str, str, float]], a: str, b: str) -> None:
    """Reorder in place so room type b sits immediately after room type a (shared wall)."""
    ia = next((i for i, r in enumerate(band) if r[0] == a), None)
    ib = next((i for i, r in enumerate(band) if r[0] == b), None)
    if ia is None or ib is None:
        return
    room = band.pop(ib)
    ia = next(i for i, r in enumerate(band) if r[0] == a)
    band.insert(ia + 1, room)


def _floor(
    fp: Rect,
    level: int,
    rooms: list[tuple[str, str, float]],
    split: float,
    rng: random.Random,
    corridor_w: float,
    stair: bool,
) -> Floor:
    rooms = list(rooms)
    rng.shuffle(rooms)
    if level == 0:  # prefer living room at the front on the ground floor
        rooms.sort(key=lambda r: r[0] != "living")
    if len(rooms) <= 2 and not stair:
        single = _fill_band(fp, rooms, level, None)
        return Floor(level=level, footprint=fp, corridor=None, stair=None, rooms=single)
    front_d = round((fp.d - corridor_w) * split, 2)
    rear_d = round(fp.d - corridor_w - front_d, 2)
    front = Rect(x=fp.x, y=fp.y, w=fp.w, d=front_d)
    corridor = Rect(x=fp.x, y=fp.y + front_d, w=fp.w, d=corridor_w)
    rear = Rect(x=fp.x, y=fp.y + front_d + corridor_w, w=fp.w, d=rear_d)
    stair_rect = None
    if stair:  # stair at the right end of the rear band, same place on every floor
        stair_rect = Rect(x=round(fp.x + fp.w - STAIR_W, 2), y=rear.y, w=STAIR_W, d=min(STAIR_D, rear_d))
        rear = Rect(x=rear.x, y=rear.y, w=round(rear.w - STAIR_W, 2), d=rear.d)
    # Alternate rooms between bands by area so both bands carry similar load.
    front_rooms: list[tuple[str, str, float]] = []
    rear_rooms: list[tuple[str, str, float]] = []
    # Kitchen and dining go in the same band, side by side (they share a wall and a door path).
    pair = {"kitchen", "dining"}
    for r in rooms:
        if r[0] in pair:
            partner = next(
                (b for b in (front_rooms, rear_rooms) if any(x[0] in pair - {r[0]} for x in b)), None
            )
            if partner is not None:
                partner.append(r)
                continue
        fa = sum(x[2] for x in front_rooms) / max(front.area, 1e-9)
        ra = sum(x[2] for x in rear_rooms) / max(rear.area, 1e-9)
        (front_rooms if fa <= ra else rear_rooms).append(r)
    if not rear_rooms:
        rear_rooms.append(front_rooms.pop())
    for band in (front_rooms, rear_rooms):
        _keep_together(band, "kitchen", "dining")
    return Floor(
        level=level,
        footprint=fp,
        corridor=corridor,
        stair=stair_rect,
        rooms=_fill_band(front, front_rooms, level, "rear") + _fill_band(rear, rear_rooms, level, "front"),
    )


def _score(opt: LayoutOption) -> Score:
    rooms = [r for f in opt.floors for r in f.rooms]
    by_type: dict[str, list[Room]] = {}
    for r in rooms:
        by_type.setdefault(r.type, []).append(r)
    pairs = [("kitchen", "dining"), ("dining", "living"), ("kitchen", "living")]
    wanted = [(a, b) for a, b in pairs if a in by_type and b in by_type]
    met = sum(any(x.rect.touches(y.rect) for x in by_type[a] for y in by_type[b]) for a, b in wanted)
    adjacency = met / len(wanted) if wanted else 1.0
    ground = opt.floors[0]
    living = by_type.get("living", [])
    living_at_front = 1.0 if living and living[0].rect.y <= ground.footprint.y + 1e-6 else 0.0
    area_match = 1 - sum(abs(r.rect.area - r.target_area_m2) / r.target_area_m2 for r in rooms) / len(rooms)
    used = sum(r.rect.area for r in rooms)
    efficiency = used / sum(f.footprint.area for f in opt.floors)
    total = 0.35 * adjacency + 0.15 * living_at_front + 0.3 * max(area_match, 0) + 0.2 * efficiency
    return Score(
        total=round(total, 4),
        adjacency=round(adjacency, 4),
        living_at_front=living_at_front,
        area_match=round(area_match, 4),
        efficiency=round(efficiency, 4),
    )


def _mirror(floor: Floor) -> Floor:
    """Flip a floor left-right inside its footprint (stair and wet wall move to the other side)."""
    fp = floor.footprint

    def flip(r: Rect) -> Rect:
        return Rect(x=round(2 * fp.x + fp.w - r.x - r.w, 2), y=r.y, w=r.w, d=r.d)

    rooms = [r.model_copy(update={"rect": flip(r.rect)}) for r in floor.rooms]
    return floor.model_copy(
        update={
            "rooms": rooms,
            "corridor": flip(floor.corridor) if floor.corridor else None,
            "stair": flip(floor.stair) if floor.stair else None,
        }
    )


def _signature(opt: LayoutOption, mirrored: bool) -> tuple[object, ...]:
    """What makes two options genuinely different to a client: proportions, which rooms face the
    road, and which side the stair/wet wall is on."""
    g = opt.floors[0]
    front = tuple(sorted(r.type for r in g.rooms if abs(r.rect.y - g.footprint.y) < 1e-6))
    return (g.footprint.w, g.footprint.d, front, mirrored)


def generate(brief: DesignBrief, n: int = 3, seed: int = 0, attempts: int = 90) -> list[LayoutOption]:
    """Return up to n options that pass every hard rule and differ in a meaningful way
    (best per signature), best score first."""
    from archmind.design.checks import hard_failures  # local import: checks imports layout types

    pack = load_pack(brief.rule_pack)
    per_floor = _split_floors(_room_list(brief), brief.floors)
    corridor_w = pack.value("corridor.width.min", 1.0)
    plot = Rect(x=0, y=0, w=brief.plot_width_m, d=brief.plot_depth_m)
    found: dict[str, tuple[float, int, tuple[object, ...], LayoutOption]] = {}
    for k in range(attempts):
        rng = random.Random(seed * 10_000 + k)
        fp = _footprint(brief, pack, per_floor, rng.choice([7.5, 8.5, 9.5]))
        split = rng.choice([0.45, 0.5, 0.55, 0.6])
        mirrored = rng.random() < 0.5
        floors = [
            _floor(fp, lvl, rooms, split, rng, corridor_w, stair=brief.floors > 1)
            for lvl, rooms in enumerate(per_floor)
        ]
        if mirrored:
            floors = [_mirror(f) for f in floors]
        opt = LayoutOption(id="", seed=seed * 10_000 + k, rule_pack=pack.id, plot=plot, floors=floors)
        if hard_failures(opt, brief, pack):
            continue
        score = _score(opt)
        opt.score = score
        key = "|".join(
            f"{r.name}@{r.rect.x},{r.rect.y},{r.rect.w},{r.rect.d}" for f in floors for r in f.rooms
        )
        if key not in found:
            found[key] = (score.total, opt.seed, _signature(opt, mirrored), opt)
    by_score = sorted(found.values(), key=lambda t: (-t[0], t[1]))
    # Fill n slots in passes: first options that differ in proportions or road-facing rooms, then
    # mirror images, then any other distinct layout.
    picked: list[tuple[tuple[object, ...], LayoutOption]] = []
    for depth in (3, 4, 0):  # 0 = no diversity requirement
        for _, _, sig, o in by_score:
            if len(picked) >= n or any(o is p for _, p in picked):
                continue
            if depth and any(s[:depth] == sig[:depth] for s, _ in picked):
                continue
            picked.append((sig, o))
    ranked = [o for _, o in picked]
    for i, o in enumerate(ranked):
        o.id = f"option-{i + 1}"
    return ranked
