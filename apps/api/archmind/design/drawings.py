"""Plan drawings (ARCH-150): one SVG per floor plus a room schedule. Concept level, not for construction."""

from xml.sax.saxutils import escape

from pydantic import BaseModel

from archmind.design.layout import LayoutOption
from archmind.design.units import Unit, area, bare_length, length
from archmind.design.walls import openings, walls

SCALE = 40  # px per metre
MARGIN = 60


class ScheduleRow(BaseModel):
    floor: int
    room_id: str
    name: str
    width_m: float
    depth_m: float
    area_m2: float


def schedule(opt: LayoutOption) -> list[ScheduleRow]:
    return [
        ScheduleRow(
            floor=r.floor,
            room_id=r.id,
            name=r.name,
            width_m=r.rect.w,
            depth_m=r.rect.d,
            area_m2=round(r.rect.area, 2),
        )
        for f in opt.floors
        for r in f.rooms
    ]


def plan_svg(opt: LayoutOption, level: int, project: str = "ArchMind project", unit: Unit = "m") -> str:
    floor = opt.floors[level]
    pw, pd = opt.plot.w * SCALE, opt.plot.d * SCALE
    W, H = pw + 2 * MARGIN, pd + 2 * MARGIN + 70

    def X(v: float) -> float:
        return round(MARGIN + v * SCALE, 1)

    def Y(v: float) -> float:  # road (front) at the bottom of the sheet
        return round(MARGIN + pd - v * SCALE, 1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" font-family="sans-serif">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<rect x="{X(0)}" y="{Y(opt.plot.d)}" width="{pw}" height="{pd}" fill="none" stroke="#999" stroke-dasharray="6 4"/>',
        f'<text x="{X(opt.plot.w / 2)}" y="{Y(0) + 16}" font-size="11" text-anchor="middle" fill="#666">ROAD / FRONT</text>',
    ]
    for r in floor.rooms:
        rc = r.rect
        cx, cy = X(rc.x + rc.w / 2), Y(rc.y + rc.d / 2)
        parts.append(
            f'<rect x="{X(rc.x)}" y="{Y(rc.y + rc.d)}" width="{rc.w * SCALE:.1f}" height="{rc.d * SCALE:.1f}" fill="#f4f1ea"/>'
        )
        detail = f"{area(rc.area, unit)} ({bare_length(rc.w, unit)} × {length(rc.d, unit)})"
        room_px = rc.w * SCALE - 8
        # ponytail: ~0.6 em per character estimate; exact text metrics would need a font engine.
        name_fs = min(12.0, room_px / (0.6 * len(r.name)))
        detail_fs = min(10.0, room_px / (0.6 * len(detail)))
        parts.append(
            f'<text x="{cx}" y="{cy - 4}" font-size="{name_fs:.1f}" text-anchor="middle">{escape(r.name)}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="{cy + 12}" font-size="{detail_fs:.1f}" text-anchor="middle" fill="#555">{detail}</text>'
        )
    if floor.stair is not None:
        s = floor.stair
        parts.append(
            f'<rect x="{X(s.x)}" y="{Y(s.y + s.d)}" width="{s.w * SCALE:.1f}" height="{s.d * SCALE:.1f}" fill="#e6e6e6"/>'
        )
        parts.append(
            f'<text x="{X(s.x + s.w / 2)}" y="{Y(s.y + s.d / 2)}" font-size="10" text-anchor="middle">STAIR</text>'
        )
    for w in walls(floor):
        sw = w.thickness * SCALE
        parts.append(
            f'<line x1="{X(w.x1)}" y1="{Y(w.y1)}" x2="{X(w.x2)}" y2="{Y(w.y2)}" stroke="#222" stroke-width="{sw:.1f}"/>'
        )
    for o in openings(floor):
        half = o.width / 2
        x1, y1, x2, y2 = (
            (o.x - half, o.y, o.x + half, o.y) if o.horizontal else (o.x, o.y - half, o.x, o.y + half)
        )
        colour = "#c0392b" if o.kind == "door" else "#2e86c1"
        parts.append(
            f'<line x1="{X(x1)}" y1="{Y(y1)}" x2="{X(x2)}" y2="{Y(y2)}" stroke="{colour}" stroke-width="5"/>'
        )
    fp = floor.footprint
    parts.append(
        f'<text x="{X(fp.x + fp.w / 2)}" y="{Y(fp.y + fp.d) - 8}" font-size="11" text-anchor="middle">{length(fp.w, unit)}</text>'
    )
    parts.append(
        f'<text x="{X(fp.x + fp.w) + 8}" y="{Y(fp.y + fp.d / 2)}" font-size="11">{length(fp.d, unit)}</text>'
    )
    ty = H - 50
    parts.append(f'<rect x="10" y="{ty}" width="{W - 20:.0f}" height="40" fill="none" stroke="#222"/>')
    title = f"{project} - {opt.id} - floor {level} - rule pack {opt.rule_pack} - generator {opt.generator_version}"
    parts.append(f'<text x="20" y="{ty + 17}" font-size="11">{escape(title)}</text>')
    parts.append(
        f'<text x="20" y="{ty + 32}" font-size="10" fill="#c0392b">CONCEPT - NOT FOR CONSTRUCTION. 1 m = {SCALE} px. Red: doors, blue: windows.</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)
