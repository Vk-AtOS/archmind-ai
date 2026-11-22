"""IFC4 model generator (ARCH-149). Deterministic GlobalIds; walls, slabs, spaces, doors, windows, stair.

Doors and windows sit in IfcOpeningElement voids cut into their host walls. Walls are centreline boxes.
"""

import uuid

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.guid
import numpy as np

from archmind.design.layout import LayoutOption
from archmind.design.walls import STOREY_HEIGHT, Opening, Wall, openings, walls

NAMESPACE = uuid.UUID("6f1c2b8e-2b7a-4e8a-9a0e-7b1b3c6d5e4f")
SLAB_DEPTH = 0.15


def _gid(key: str) -> str:
    return str(ifcopenshell.guid.compress(uuid.uuid5(NAMESPACE, key).hex))


def _place(
    f: ifcopenshell.file,
    product: ifcopenshell.entity_instance,
    x: float,
    y: float,
    z: float,
    angle: float = 0.0,
) -> None:
    m = np.eye(4)
    c, s = np.cos(angle), np.sin(angle)
    m[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    m[:3, 3] = [x, y, z]
    ifcopenshell.api.geometry.edit_object_placement(f, product=product, matrix=m)


def _host(
    hosts: list[tuple[Wall, ifcopenshell.entity_instance]], o: Opening
) -> tuple[Wall, ifcopenshell.entity_instance] | None:
    """The wall whose centreline contains the opening's centre."""
    for w, wall in hosts:
        if o.horizontal and abs(w.y1 - w.y2) < 1e-9 and abs(w.y1 - o.y) < 1e-6:
            if min(w.x1, w.x2) - 1e-6 <= o.x <= max(w.x1, w.x2) + 1e-6:
                return w, wall
        if not o.horizontal and abs(w.x1 - w.x2) < 1e-9 and abs(w.x1 - o.x) < 1e-6:
            if min(w.y1, w.y2) - 1e-6 <= o.y <= max(w.y1, w.y2) + 1e-6:
                return w, wall
    return None


def _stable_ids(f: ifcopenshell.file, key: str) -> None:
    """Relationships and property sets created by the API get random GUIDs, and their creation
    order is not stable. Derive each GUID from what the record links (deterministic object ids)."""
    for rel in f.by_type("IfcRelDefinesByProperties"):
        objs = ",".join(sorted(o.GlobalId for o in rel.RelatedObjects))
        pset = rel.RelatingPropertyDefinition
        pset.GlobalId = _gid(f"{key}/pset/{pset.Name}/{objs}")
        rel.GlobalId = _gid(f"{key}/defines/{pset.Name}/{objs}")
    for rel in f.by_type("IfcRelationship"):
        if rel.is_a("IfcRelDefinesByProperties"):
            continue
        linked: list[str] = []
        for value in rel:  # type: ignore[attr-defined]  # entity_instance iterates its attributes
            items = value if isinstance(value, tuple) else (value,)
            linked += [
                v.GlobalId for v in items if isinstance(v, ifcopenshell.entity_instance) and v.is_a("IfcRoot")
            ]
        rel.GlobalId = _gid(f"{key}/{rel.is_a()}/{','.join(sorted(linked))}")


def build(opt: LayoutOption, project_name: str = "ArchMind project") -> ifcopenshell.file:
    f = ifcopenshell.api.project.create_file(version="IFC4")
    key = f"{opt.rule_pack}/{opt.seed}/{opt.id}"

    def entity(cls: str, name: str, ident: str) -> ifcopenshell.entity_instance:
        e = ifcopenshell.api.root.create_entity(f, ifc_class=cls, name=name)
        e.GlobalId = _gid(f"{key}/{ident}")
        return e

    project = entity("IfcProject", project_name, "project")
    ifcopenshell.api.unit.assign_unit(f, length={"is_metric": True, "raw": "METERS"})
    model = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model
    )
    site = entity("IfcSite", "Site", "site")
    building = entity("IfcBuilding", "House", "building")
    ifcopenshell.api.aggregate.assign_object(f, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(f, products=[building], relating_object=site)

    for floor in opt.floors:
        z = floor.level * STOREY_HEIGHT
        storey = entity("IfcBuildingStorey", f"Floor {floor.level}", f"storey/{floor.level}")
        storey.Elevation = z
        ifcopenshell.api.aggregate.assign_object(f, products=[storey], relating_object=building)
        contained: list[ifcopenshell.entity_instance] = []

        fp = floor.footprint
        slab = entity("IfcSlab", f"Floor slab {floor.level}", f"slab/{floor.level}")
        rep = ifcopenshell.api.geometry.add_slab_representation(
            f, context=body, depth=SLAB_DEPTH, polyline=[(0, 0), (fp.w, 0), (fp.w, fp.d), (0, fp.d)]
        )
        ifcopenshell.api.geometry.assign_representation(f, product=slab, representation=rep)
        _place(f, slab, fp.x, fp.y, z - SLAB_DEPTH)
        contained.append(slab)

        hosts: list[tuple[Wall, ifcopenshell.entity_instance]] = []
        for w in walls(floor):
            wall = entity(
                "IfcWall", ("External" if w.external else "Internal") + f" wall {w.id}", f"wall/{w.id}"
            )
            rep = ifcopenshell.api.geometry.add_wall_representation(
                f,
                context=body,
                length=w.length,
                height=STOREY_HEIGHT,
                thickness=w.thickness,
                offset=-w.thickness / 2,
            )
            ifcopenshell.api.geometry.assign_representation(f, product=wall, representation=rep)
            horizontal = abs(w.y2 - w.y1) < 1e-9
            _place(f, wall, w.x1, w.y1, z, 0.0 if horizontal else np.pi / 2)
            contained.append(wall)
            hosts.append((w, wall))

        for o in openings(floor):
            cls = "IfcDoor" if o.kind == "door" else "IfcWindow"
            el = entity(cls, o.id, f"opening/{o.id}")
            height, sill = (2.1, 0.0) if o.kind == "door" else (1.2, 0.9)
            el.OverallWidth = o.width
            el.OverallHeight = height
            angle = 0.0 if o.horizontal else np.pi / 2
            # Start of the opening along its wall (placement origin is the start, not the centre).
            sx, sy = (o.x - o.width / 2, o.y) if o.horizontal else (o.x, o.y - o.width / 2)
            _place(f, el, sx, sy, z + sill, angle)
            contained.append(el)
            host = _host(hosts, o)
            if host is None:  # opening not on any wall line: keep the element, report no void
                continue
            w, wall = host
            void = entity("IfcOpeningElement", f"Opening {o.id}", f"void/{o.id}")
            t = w.thickness + 0.02  # slightly thicker than the wall so the cut is clean
            rep = ifcopenshell.api.geometry.add_wall_representation(
                f, context=body, length=o.width, height=height, thickness=t, offset=-t / 2
            )
            ifcopenshell.api.geometry.assign_representation(f, product=void, representation=rep)
            _place(f, void, sx, sy, z + sill, angle)
            ifcopenshell.api.feature.add_feature(f, feature=void, element=wall)
            ifcopenshell.api.feature.add_filling(f, opening=void, element=el)

        if floor.stair is not None:
            st = entity("IfcStair", f"Stair {floor.level}", f"stair/{floor.level}")
            _place(f, st, floor.stair.x, floor.stair.y, z)
            contained.append(st)
        ifcopenshell.api.spatial.assign_container(f, products=contained, relating_structure=storey)

        spaces = []
        for r in floor.rooms:
            sp = entity("IfcSpace", r.name, f"space/{r.id}")
            rc = r.rect
            rep = ifcopenshell.api.geometry.add_slab_representation(
                f, context=body, depth=STOREY_HEIGHT, polyline=[(0, 0), (rc.w, 0), (rc.w, rc.d), (0, rc.d)]
            )
            ifcopenshell.api.geometry.assign_representation(f, product=sp, representation=rep)
            _place(f, sp, rc.x, rc.y, z)
            pset = ifcopenshell.api.pset.add_pset(f, product=sp, name="ArchMind_Room")
            ifcopenshell.api.pset.edit_pset(
                f,
                pset=pset,
                properties={
                    "RoomId": r.id,
                    "RoomType": r.type,
                    "TargetArea": r.target_area_m2,
                    "Area": round(rc.area, 3),
                },
            )
            spaces.append(sp)
        ifcopenshell.api.aggregate.assign_object(f, products=spaces, relating_object=storey)
    _stable_ids(f, key)
    return f
