"use client";

// 3D view of one room with its finishes and items (ARCH-156). Display only.
// World axes: room-local x -> world x, room-local y (from the front wall) -> world -z, so viewed from
// the front the room reads like the plan (x to the right). Walls face inwards and are single-sided,
// so the walls nearest the camera disappear and the room stays visible from any angle.
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { buildItem } from "@/lib/furniture3d";
import { type CatalogItem, type Finish, type Placement, type RoomFinish, type RoomInfo, type Side, standHeight } from "@/lib/interior";
import { finishTexture, TILE } from "@/lib/textures";

const WALL_H = 2.85;
const DOOR_H = 2.1;
const SILL = 0.9;
const HEAD = 2.1;

type Props = {
  room: RoomInfo;
  finish: RoomFinish;
  items: Placement[];
  byId: Map<string, CatalogItem>;
  walls: Map<string, Finish>;
  floors: Map<string, Finish>;
  selected: string | null;
  onSelect: (uid: string | null) => void;
};

function texturedMat(f: Finish, colour: string | null | undefined, uw: number, vh: number, u0 = 0, v0 = 0) {
  const t = finishTexture(f.pattern, colour || f.colour).clone();
  t.needsUpdate = true;
  t.repeat.set(uw / TILE, vh / TILE);
  t.offset.set(u0 / TILE, v0 / TILE);
  return new THREE.MeshStandardMaterial({ map: t, roughness: 0.9 });
}

export default function Room3D({ room, finish, items, byId, walls, floors, selected, onSelect }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const ctx = useRef<{
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    content: THREE.Group;
    renderer: THREE.WebGLRenderer;
  } | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Renderer, camera and controls live as long as the component.
  useEffect(() => {
    const el = host.current!;
    const width = el.clientWidth;
    const height = 440;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf5f5f4);
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.05, 200);
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    el.appendChild(renderer.domElement);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xd8cfc4, 1.1));
    const sun = new THREE.DirectionalLight(0xfff4e0, 1.4);
    sun.position.set(6, 9, 5);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    scene.add(sun);
    scene.add(sun.target);
    const content = new THREE.Group();
    scene.add(content);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.maxPolarAngle = Math.PI / 2 - 0.05;
    ctx.current = { scene, camera, controls, content, renderer };

    // Click (not drag) selects an item.
    let down: [number, number] | null = null;
    const ray = new THREE.Raycaster();
    const onDown = (e: PointerEvent) => (down = [e.clientX, e.clientY]);
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
      const r = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
      const hit = ray.intersectObjects(content.children, true).find((h) => {
        let o: THREE.Object3D | null = h.object;
        while (o && !o.userData.uid) o = o.parent;
        return o;
      });
      let o: THREE.Object3D | null = hit?.object ?? null;
      while (o && !o.userData.uid) o = o.parent;
      onSelectRef.current((o?.userData.uid as string) ?? null);
    };
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);

    let frame = 0;
    const tick = () => {
      frame = requestAnimationFrame(tick);
      controls.update();
      renderer.render(scene, camera);
    };
    tick();
    return () => {
      cancelAnimationFrame(frame);
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      controls.dispose();
      dispose(content);
      renderer.dispose();
      el.removeChild(renderer.domElement);
      ctx.current = null;
    };
  }, []);

  // Re-aim the camera when the room changes.
  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    const dist = Math.max(room.w, room.d) * 1.15 + 1.5;
    c.camera.position.set(room.w / 2 + dist * 0.35, WALL_H + dist * 0.55, dist * 0.75);
    c.controls.target.set(room.w / 2, 0.6, -room.d / 2);
    c.controls.update();
  }, [room.id, room.w, room.d]);

  // Rebuild the room contents whenever finishes or items change.
  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    dispose(c.content);
    c.content.clear();
    const g = c.content;

    const fl = floors.get(finish.floor);
    if (fl) {
      const floor = new THREE.Mesh(new THREE.PlaneGeometry(room.w, room.d), texturedMat(fl, null, room.w, room.d));
      floor.rotation.x = -Math.PI / 2;
      floor.position.set(room.w / 2, 0, -room.d / 2);
      floor.receiveShadow = true;
      g.add(floor);
    }

    const sides: [Side, number][] = [
      ["front", room.w],
      ["rear", room.w],
      ["left", room.d],
      ["right", room.d],
    ];
    for (const [side, len] of sides) {
      const fid = finish.feature && finish.feature_side === side ? finish.feature : finish.wall;
      const wf = walls.get(fid);
      if (!wf) continue;
      const colour = fid === finish.wall ? finish.wall_colour : null;
      const ops = room.openings.filter((o) => o.side === side).sort((a, b) => a.offset - b.offset);
      // wall split into rectangles around the openings: [u0, u1, v0, v1]
      const rects: [number, number, number, number][] = [];
      let u = 0;
      for (const o of ops) {
        const a = Math.max(0, o.offset - o.width / 2);
        const b = Math.min(len, o.offset + o.width / 2);
        if (a > u) rects.push([u, a, 0, WALL_H]);
        if (o.kind === "door") rects.push([a, b, DOOR_H, WALL_H]);
        else rects.push([a, b, 0, SILL], [a, b, HEAD, WALL_H]);
        addOpening(g, side, o.kind, a, b, room);
        u = Math.max(u, b);
      }
      if (u < len) rects.push([u, len, 0, WALL_H]);
      for (const [u0, u1, v0, v1] of rects) {
        const plane = new THREE.Mesh(new THREE.PlaneGeometry(u1 - u0, v1 - v0), texturedMat(wf, colour, u1 - u0, v1 - v0, u0, v0));
        place(plane, side, (u0 + u1) / 2, (v0 + v1) / 2, room);
        plane.receiveShadow = true;
        g.add(plane);
      }
    }

    for (const p of items) {
      const it = byId.get(p.item_id);
      if (!it) continue;
      const model = buildItem(it, p.colour);
      model.userData.uid = p.uid;
      const y = it.layer === "wall" ? it.elev : it.layer === "top" ? standHeight(p, items, byId) : 0;
      model.position.set(p.x, y, -p.y);
      model.rotation.y = Math.PI + (p.rot * Math.PI) / 180;
      g.add(model);
      if (p.uid === selected) {
        const helper = new THREE.BoxHelper(model, 0xf59e0b);
        g.add(helper);
      }
    }
  }, [room, finish, items, byId, walls, floors, selected]);

  return (
    <div>
      <div ref={host} className="w-full overflow-hidden rounded-md border border-stone-200" data-testid="room-3d" />
      <p className="mt-1 text-xs text-stone-500">Drag to orbit, scroll to zoom, click an item to select it. Concept visual, not a render.</p>
    </div>
  );
}

function place(m: THREE.Object3D, side: Side, u: number, v: number, room: RoomInfo) {
  if (side === "front") {
    m.position.set(u, v, 0);
    m.rotation.y = Math.PI;
  } else if (side === "rear") {
    m.position.set(u, v, -room.d);
  } else if (side === "left") {
    m.position.set(0, v, -u);
    m.rotation.y = Math.PI / 2;
  } else {
    m.position.set(room.w, v, -u);
    m.rotation.y = -Math.PI / 2;
  }
}

function addOpening(g: THREE.Group, side: Side, kind: "door" | "window", a: number, b: number, room: RoomInfo) {
  const w = b - a;
  if (kind === "window") {
    const glass = new THREE.Mesh(
      new THREE.PlaneGeometry(w, HEAD - SILL),
      new THREE.MeshStandardMaterial({ color: 0xbfe3f5, transparent: true, opacity: 0.35, roughness: 0.05 }),
    );
    place(glass, side, (a + b) / 2, (SILL + HEAD) / 2, room);
    g.add(glass);
    const frame = new THREE.Mesh(new THREE.PlaneGeometry(0.04, HEAD - SILL), new THREE.MeshStandardMaterial({ color: 0xffffff }));
    place(frame, side, (a + b) / 2, (SILL + HEAD) / 2, room);
    frame.position.add(new THREE.Vector3(0, 0, 0));
    g.add(frame);
  } else {
    const leaf = new THREE.Mesh(new THREE.PlaneGeometry(w, DOOR_H), new THREE.MeshStandardMaterial({ color: 0x8d6e63, roughness: 0.6 }));
    place(leaf, side, (a + b) / 2, DOOR_H / 2, room);
    g.add(leaf);
  }
}

function dispose(root: THREE.Object3D) {
  root.traverse((o) => {
    if (o instanceof THREE.Mesh || o instanceof THREE.LineSegments) {
      o.geometry.dispose();
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      for (const m of mats) {
        (m as THREE.MeshStandardMaterial).map?.dispose();
        m.dispose();
      }
    }
  });
}
