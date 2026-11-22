import xml.etree.ElementTree as ET
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pytest

from archmind.design.drawings import plan_svg, schedule
from archmind.design.estimate import RateTable, estimate, load_rates
from archmind.design.geometry import Rect
from archmind.design.ifc import build
from archmind.design.layout import Floor, LayoutOption, Room, generate
from archmind.design.quantities import compute
from archmind.design.walls import walls
from tests.test_design import BRIEFS


def tiny() -> LayoutOption:
    """6 x 4 m single floor: living 4 x 4 + kitchen 2 x 4, no corridor. Hand-checkable."""
    fp = Rect(x=1, y=3, w=6, d=4)
    rooms = [
        Room(
            id="F0-Living",
            type="living",
            name="Living",
            floor=0,
            rect=Rect(x=1, y=3, w=4, d=4),
            target_area_m2=16,
        ),
        Room(
            id="F0-Kitchen",
            type="kitchen",
            name="Kitchen",
            floor=0,
            rect=Rect(x=5, y=3, w=2, d=4),
            target_area_m2=8,
        ),
    ]
    return LayoutOption(
        id="tiny",
        seed=0,
        rule_pack="generic-metric-v0",
        plot=Rect(x=0, y=0, w=8, d=9),
        floors=[Floor(level=0, footprint=fp, corridor=None, stair=None, rooms=rooms)],
    )


def test_quantities_match_hand_calculation() -> None:
    q = compute(tiny())
    assert q.get("ext_wall_length").qty == 20.0  # perimeter 2 x (6 + 4)
    assert q.get("int_wall_length").qty == 4.0  # shared edge at x = 5
    assert q.get("ext_wall_area").qty == 60.0
    assert q.get("masonry_volume").qty == pytest.approx(20 * 3 * 0.23 + 4 * 3 * 0.115)
    assert q.get("built_up_area").qty == 24.0
    assert q.get("carpet_area").qty == 24.0
    assert q.get("slab_area").qty == 24.0  # roof only
    assert q.get("door_count").qty == 1  # entrance; no corridor doors without a corridor
    assert q.get("window_count").qty == 6  # 3 external edges per room


def test_estimate_is_quantity_times_rate_and_labelled_sample() -> None:
    q = compute(tiny())
    table = load_rates("sample-inr-v0")
    est = estimate(q, table)
    assert est.total == pytest.approx(sum(q.get(r.item_id).qty * r.rate for r in table.rates), abs=0.01)
    assert est.currency == "INR"
    assert any("sample" in w for w in est.warnings)
    assert "not a quotation" in est.label


def test_estimate_rejects_unit_mismatch() -> None:
    bad = load_rates("sample-inr-v0").model_copy(deep=True)
    bad.rates[0].unit = "m2"  # masonry is in m3
    with pytest.raises(ValueError, match="unit mismatch"):
        estimate(compute(tiny()), RateTable.model_validate(bad.model_dump()))


def test_rate_table_rejects_path_tricks() -> None:
    with pytest.raises(ValueError):
        load_rates("../x")


def test_plan_svg_is_valid_and_labels_every_room() -> None:
    opt = generate(BRIEFS[0])[0]
    for level, floor in enumerate(opt.floors):
        svg = plan_svg(opt, level)
        ET.fromstring(svg)  # well-formed XML
        for r in floor.rooms:
            assert r.name in svg
        assert "NOT FOR CONSTRUCTION" in svg
    assert len(schedule(opt)) == sum(len(f.rooms) for f in opt.floors)


def _bbox(settings: ifcopenshell.geom.settings, product: ifcopenshell.entity_instance) -> np.ndarray:
    shape = ifcopenshell.geom.create_shape(settings, product)
    v = np.array(shape.geometry.verts).reshape(-1, 3)
    return np.array([v.min(axis=0), v.max(axis=0)])


def test_ifc_reads_back_matching_the_layout(tmp_path: Path) -> None:
    opt = generate(BRIEFS[0])[0]
    path = tmp_path / "house.ifc"
    build(opt).write(str(path))
    f = ifcopenshell.open(str(path))
    rooms = {r.name: r for fl in opt.floors for r in fl.rooms}
    spaces = f.by_type("IfcSpace")
    assert sorted(s.Name for s in spaces) == sorted(rooms)
    assert len(f.by_type("IfcWall")) == sum(len(walls(fl)) for fl in opt.floors)
    assert len(f.by_type("IfcBuildingStorey")) == len(opt.floors)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    for s in spaces:
        r = rooms[s.Name]
        lo, hi = _bbox(settings, s)
        assert lo[0] == pytest.approx(r.rect.x, abs=1e-3)
        assert lo[1] == pytest.approx(r.rect.y, abs=1e-3)
        assert hi[0] - lo[0] == pytest.approx(r.rect.w, abs=1e-3)
        assert hi[1] - lo[1] == pytest.approx(r.rect.d, abs=1e-3)


def test_ifc_global_ids_are_deterministic() -> None:
    opt = generate(BRIEFS[3])[0]
    ids_a = sorted(e.GlobalId for e in build(opt).by_type("IfcRoot"))
    ids_b = sorted(e.GlobalId for e in build(opt).by_type("IfcRoot"))
    assert ids_a == ids_b
    assert len(set(ids_a)) == len(ids_a)
