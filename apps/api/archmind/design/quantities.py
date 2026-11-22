"""Deterministic quantity engine (ARCH-84, ARCH-85). Methods are documented per line; centreline model,
gross wall areas (openings not deducted), no foundations or MEP. See ARCH-84 for limits."""

from pydantic import BaseModel

from archmind.design.layout import LayoutOption
from archmind.design.walls import STOREY_HEIGHT, openings, walls

QUANTITY_VERSION = "0.1.0"
SLAB_DEPTH = 0.15


class QuantityLine(BaseModel):
    item_id: str
    description: str
    qty: float
    unit: str
    method: str


class Quantities(BaseModel):
    option_id: str
    version: str = QUANTITY_VERSION
    lines: list[QuantityLine]

    def get(self, item_id: str) -> QuantityLine:
        return next(line for line in self.lines if line.item_id == item_id)


def compute(opt: LayoutOption) -> Quantities:
    ext_len = int_len = ext_vol = int_vol = 0.0
    doors = windows = 0
    for f in opt.floors:
        for w in walls(f):
            vol = w.length * STOREY_HEIGHT * w.thickness
            if w.external:
                ext_len += w.length
                ext_vol += vol
            else:
                int_len += w.length
                int_vol += vol
        for o in openings(f):
            if o.kind == "door":
                doors += 1
            else:
                windows += 1
    built_up = sum(f.footprint.area for f in opt.floors)
    carpet = sum(r.rect.area for f in opt.floors for r in f.rooms)
    roof = opt.floors[-1].footprint.area
    q = [
        ("built_up_area", "Built-up area (all floors)", built_up, "m2", "sum of footprint areas"),
        ("carpet_area", "Carpet area (rooms)", carpet, "m2", "sum of room centreline areas"),
        ("ext_wall_length", "External wall length", ext_len, "m", "centreline, all floors"),
        ("int_wall_length", "Internal wall length", int_len, "m", "centreline, all floors"),
        (
            "ext_wall_area",
            "External wall area",
            ext_len * STOREY_HEIGHT,
            "m2",
            f"length x {STOREY_HEIGHT} m, gross",
        ),
        (
            "int_wall_area",
            "Internal wall area",
            int_len * STOREY_HEIGHT,
            "m2",
            f"length x {STOREY_HEIGHT} m, gross",
        ),
        ("masonry_volume", "Masonry volume", ext_vol + int_vol, "m3", "wall area x thickness, gross"),
        (
            "slab_area",
            "RCC slab area (floors above ground + roof)",
            built_up - opt.floors[0].footprint.area + roof,
            "m2",
            "footprints of upper floors plus roof",
        ),
        (
            "slab_volume",
            "RCC slab volume",
            (built_up - opt.floors[0].footprint.area + roof) * SLAB_DEPTH,
            "m3",
            f"slab area x {SLAB_DEPTH} m",
        ),
        ("flooring_area", "Flooring area", built_up, "m2", "built-up area (includes corridor and stair)"),
        (
            "plaster_area",
            "Plaster area",
            2 * (ext_len + int_len) * STOREY_HEIGHT,
            "m2",
            "both faces of every wall, gross",
        ),
        ("door_count", "Doors", doors, "no", "one per room plus main entrance"),
        ("window_count", "Windows", windows, "no", "one per external room edge"),
    ]
    return Quantities(
        option_id=opt.id,
        lines=[
            QuantityLine(item_id=i, description=d, qty=round(v, 3), unit=u, method=m) for i, d, v, u, m in q
        ],
    )
