"""Interior studio (ARCH-156): catalogue, auto-furnish, fit checks, cost, save with revision guard."""

import pytest
from fastapi.testclient import TestClient

from archmind.design.brief import DesignBrief
from archmind.design.furnish import furnish
from archmind.design.interior import Interior, Placement, catalog, cost, fit_issues, room_info
from archmind.design.layout import generate
from tests.test_api import BRIEF, add_user, org_admin

THEMES = [t.id for t in catalog().themes]
LAYOUTS = generate(DesignBrief.model_validate(BRIEF))


def test_catalogue_has_furniture_decor_plants_and_finishes() -> None:
    cat = catalog()
    cats = {i.category for i in cat.items}
    assert cats == {"furniture", "fixture", "decor", "plant"}
    names = " ".join(i.name for i in cat.items)
    assert "Buddha" in names and "Monstera" in names and "Tulsi" in names
    assert {f.pattern for f in cat.wall_finishes} >= {"paint", "brick", "wood", "stone", "floral"}
    for t in cat.themes:  # every theme points at real catalogue entries
        Interior(theme=t.id, rooms={}, items=[])
        assert all(cat.has("item", x) for xs in t.extras.values() for x in xs)


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("layout", LAYOUTS, ids=[x.id for x in LAYOUTS])
def test_auto_furnish_every_theme_has_no_hard_failures(theme: str, layout: object) -> None:
    it = furnish(layout, theme)  # type: ignore[arg-type]
    assert not [i for i in fit_issues(layout, it) if i.result == "fail"]  # type: ignore[arg-type]
    kinds = {(p.room_id.split("-")[1].rstrip("0123456789"), catalog().item(p.item_id).kind) for p in it.items}
    assert {("Bedroom", "bed"), ("Living", "sofa"), ("Kitchen", "counter"), ("Bathroom", "wc")} <= kinds
    assert set(it.rooms) == {r.id for r in room_info(layout)}  # type: ignore[arg-type]  # every room finished
    assert furnish(layout, theme) == it  # type: ignore[arg-type]  # deterministic


def test_fit_checks_catch_overlap_door_and_outside() -> None:
    layout = LAYOUTS[0]
    bed = next(r for r in room_info(layout) if r.type == "bedroom")
    door = next(o for o in bed.openings if o.kind == "door")
    dy = 0.5 if door.side == "front" else bed.d - 0.5
    items = [
        Placement(uid="a", item_id="bed_single", room_id=bed.id, x=bed.w / 2, y=bed.d / 2),
        Placement(uid="b", item_id="armchair", room_id=bed.id, x=bed.w / 2, y=bed.d / 2),  # on the bed
        Placement(uid="c", item_id="bookshelf", room_id=bed.id, x=door.offset, y=dy),  # in the door swing
        Placement(uid="d", item_id="side_table", room_id=bed.id, x=bed.w + 1, y=1),  # outside
        Placement(uid="e", item_id="counter_1800", room_id=bed.id, x=1, y=1),  # kitchen item in a bedroom
    ]
    it = Interior(theme="modern", rooms={}, items=items)
    rules = {(i.uid, i.rule) for i in fit_issues(layout, it) if i.result == "fail"}
    assert ("b", "item.overlap") in rules and ("c", "item.door_clear") in rules
    assert ("d", "item.inside_room") in rules and ("e", "item.room_type") in rules


def test_cost_prices_items_and_finishes_and_feature_wall_changes_it() -> None:
    layout = LAYOUTS[0]
    it = furnish(layout, "modern")
    c = cost(layout, it)
    groups = {line.group for line in c.lines}
    assert {"Furniture", "Fixtures", "Wall finishes", "Floor finishes"} <= groups
    assert c.total == pytest.approx(sum(line.amount for line in c.lines))
    room = next(iter(it.rooms))
    it.rooms[room].feature, it.rooms[room].feature_side = "stone_cladding", "rear"
    assert cost(layout, it).total > c.total  # stone cladding costs more than paint


def test_interior_validation_rejects_unknown_ids() -> None:
    with pytest.raises(ValueError):
        Interior(theme="baroque", rooms={}, items=[])
    with pytest.raises(ValueError):
        Interior(theme="modern", rooms={}, items=[Placement(uid="x", item_id="unicorn", room_id="r")])


def test_interior_api_auto_edit_save_and_conflict(client: TestClient) -> None:
    a, _ = org_admin(client)
    pr = a.post("/api/v1/projects", json={"name": "Interiors", "location": ""}).json()
    opt = a.post(f"/api/v1/projects/{pr['id']}/briefs", json=BRIEF).json()["options"][0]["id"]
    base = f"/api/v1/options/{opt}/interior"

    assert len(a.get("/api/v1/interiors/catalog").json()["items"]) > 40
    first = a.get(base).json()
    assert first["saved"] is False and first["revision"] == 0 and first["can_edit"] is True
    assert first["interior"]["theme"] == "modern" and len(first["interior"]["items"]) > 10

    trad = a.post(f"{base}/auto", json={"theme": "traditional"}).json()
    assert any(p["item_id"] == "pooja_unit" for p in trad["interior"]["items"])

    # swap the sofa, add a Buddha statue and a plant, recolour the walls; check without saving
    it = trad["interior"]
    living = next(r for r in trad["rooms"] if r["type"] == "living")
    sofa = next(p for p in it["items"] if p["item_id"] == "sofa_wooden")
    sofa["item_id"], sofa["colour"] = "sofa_leather", "#334455"
    it["items"].append(
        {"uid": "new-1", "item_id": "buddha_floor", "room_id": living["id"], "x": 0.4, "y": 0.4, "rot": 0}
    )
    it["rooms"][living["id"]].update(wall="paint_sage", wall_colour="#aabbcc")
    checked = a.post(f"{base}/check", json={"interior": it, "base_revision": 0}).json()
    assert checked["saved"] is False and "issues" in checked

    saved = a.put(base, json={"interior": it, "base_revision": 0})
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    again = a.get(base).json()
    assert again["saved"] is True and any(p["item_id"] == "sofa_leather" for p in again["interior"]["items"])
    assert a.put(base, json={"interior": it, "base_revision": 0}).status_code == 409  # stale revision
    assert a.put(base, json={"interior": it, "base_revision": 1}).json()["revision"] == 2

    bad = dict(
        it, items=[{"uid": "z", "item_id": "sofa_leather", "room_id": "F9-Nowhere", "x": 1, "y": 1, "rot": 0}]
    )
    assert a.put(base, json={"interior": bad, "base_revision": 2}).status_code == 422

    viewer = add_user(a, "viewer")
    assert viewer.get(base).json()["can_edit"] is False
    assert viewer.put(base, json={"interior": it, "base_revision": 2}).status_code == 403
    other, _ = org_admin(client)
    assert other.get(base).status_code == 404  # tenant isolation
