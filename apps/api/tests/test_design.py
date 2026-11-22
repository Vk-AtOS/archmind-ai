import pytest
from pydantic import ValidationError

from archmind.design.brief import DesignBrief
from archmind.design.checks import run_checks
from archmind.design.geometry import Rect
from archmind.design.layout import generate
from archmind.design.rules import load_pack

SB = {"front": 3.0, "rear": 1.5, "left": 1.0, "right": 1.0}


def brief(w: float, d: float, floors: int, beds: int, baths: int, dining: bool = True) -> DesignBrief:
    rooms = [{"type": "living"}, {"type": "kitchen"}, {"type": "bedroom", "count": beds}]
    rooms.append({"type": "bathroom", "count": baths})
    if dining:
        rooms.append({"type": "dining"})
    return DesignBrief.model_validate(
        {"plot_width_m": w, "plot_depth_m": d, "setbacks": SB, "floors": floors, "rooms": rooms}
    )


# 10 synthetic briefs: common Indian and generic plot sizes, G and G+1, 2 to 4 bedrooms.
BRIEFS = [
    brief(9.0, 15.0, 2, 2, 2),
    brief(9.0, 12.0, 2, 2, 2, dining=False),
    brief(12.0, 18.0, 1, 2, 2),
    brief(12.0, 15.0, 2, 3, 2),
    brief(15.0, 18.0, 1, 3, 2),
    brief(10.0, 20.0, 2, 3, 3),
    brief(12.0, 24.0, 2, 4, 3),
    brief(15.0, 24.0, 1, 3, 2),
    brief(18.0, 18.0, 2, 4, 3),
    brief(9.0, 18.0, 2, 3, 2),
]


@pytest.mark.parametrize("b", BRIEFS, ids=[f"{b.plot_width_m}x{b.plot_depth_m}-G{b.floors}" for b in BRIEFS])
def test_every_brief_yields_three_valid_options(b: DesignBrief) -> None:
    opts = generate(b, n=3)
    assert len(opts) >= 3
    pack = load_pack(b.rule_pack)
    for o in opts:
        fails = [c for c in run_checks(o, b, pack) if c.result == "fail"]
        assert not fails, fails
        rooms = {r.name for f in o.floors for r in f.rooms}
        assert len(rooms) == sum(r.count for r in b.rooms)


def test_generation_is_deterministic() -> None:
    a = [o.model_dump() for o in generate(BRIEFS[3], seed=7)]
    b = [o.model_dump() for o in generate(BRIEFS[3], seed=7)]
    assert a == b


def test_brief_rejects_impossible_plot() -> None:
    with pytest.raises(ValidationError, match="plot allows"):
        brief(6.0, 8.0, 1, 4, 2)
    with pytest.raises(ValidationError, match="no buildable area"):
        DesignBrief.model_validate(
            {"plot_width_m": 2, "plot_depth_m": 10, "setbacks": SB, "rooms": [{"type": "living"}]}
        )


def test_check_engine_catches_seeded_defects() -> None:
    b = BRIEFS[2]
    pack = load_pack(b.rule_pack)
    opt = generate(b, n=1)[0]
    bad = opt.model_copy(deep=True)
    room = bad.floors[0].rooms[0]
    room.rect = Rect(x=room.rect.x, y=room.rect.y, w=1.0, d=1.0)  # too small and too narrow
    other = bad.floors[0].rooms[1]
    other.rect = Rect(x=room.rect.x, y=room.rect.y, w=2.0, d=2.0)  # overlaps the first room
    results = {(c.rule_id, c.subject): c.result for c in run_checks(bad, b, pack)}
    assert results[(f"room.{room.type}.area.min", room.id)] == "fail"
    assert results[(f"room.{room.type}.width.min", room.id)] == "fail"
    assert results[("rooms.no_overlap", "floor 0")] == "fail"


def test_unknown_rule_is_unknown_not_pass() -> None:
    b = BRIEFS[2]
    pack = load_pack(b.rule_pack).model_copy(deep=True)
    pack.rules = [r for r in pack.rules if r.id != "coverage.max"]
    items = run_checks(generate(b, n=1)[0], b, pack)
    assert next(c for c in items if c.rule_id == "coverage.max").result == "unknown"


def test_rule_pack_rejects_path_tricks() -> None:
    with pytest.raises(ValueError):
        load_pack("../secrets")


@pytest.mark.parametrize("b", BRIEFS, ids=[f"{b.plot_width_m}x{b.plot_depth_m}-G{b.floors}" for b in BRIEFS])
def test_rooms_stay_near_their_target_size(b: DesignBrief) -> None:
    # Guards the regression where rooms stretched to fill the whole buildable area (85 m2 living).
    for o in generate(b, n=3):
        for r in (r for f in o.floors for r in f.rooms):
            assert r.rect.area <= 2.5 * r.target_area_m2, (r.name, r.rect.area)


@pytest.mark.parametrize("b", BRIEFS, ids=[f"{b.plot_width_m}x{b.plot_depth_m}-G{b.floors}" for b in BRIEFS])
def test_options_are_genuinely_different(b: DesignBrief) -> None:
    # Regression: the three options used to be identical apart from room order.
    opts = generate(b, n=3)
    layouts = {
        tuple((r.name, r.rect.x, r.rect.y, r.rect.w, r.rect.d) for f in o.floors for r in f.rooms)
        for o in opts
    }
    assert len(layouts) == 3


@pytest.mark.parametrize(
    "b",
    [b for b in BRIEFS if any(r.type == "dining" for r in b.rooms)],
    ids=lambda b: f"{b.plot_width_m}x{b.plot_depth_m}",
)
def test_kitchen_shares_a_wall_with_dining(b: DesignBrief) -> None:
    # Owner-visible quality issue: kitchen and dining were often across the corridor.
    for o in generate(b, n=3):
        rooms = {r.type: r for f in o.floors for r in f.rooms if f.level == 0}
        assert rooms["kitchen"].rect.touches(rooms["dining"].rect), o.id
