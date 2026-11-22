"use client";

// Display-only 3D view built from the layout data (ADR-004a). Not authoritative geometry:
// the IFC download is the model of record.
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import type { Layout } from "@/lib/types";

const STOREY = 3.0;
const WALL = 0.15;
const COLOURS: Record<string, number> = {
  living: 0xe7d8c9,
  dining: 0xe9dfc4,
  kitchen: 0xd9e4cf,
  bedroom: 0xcfdbe6,
  bathroom: 0xd5e8e8,
};

function label(text: string): THREE.Sprite {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 64;
  const g = c.getContext("2d")!;
  g.fillStyle = "rgba(255,255,255,0.85)";
  g.fillRect(0, 8, 256, 48);
  g.fillStyle = "#1c1917";
  g.font = "28px system-ui, sans-serif";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(text, 128, 32);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false }));
  sprite.scale.set(2.4, 0.6, 1);
  return sprite;
}

/** level: a floor index shows that floor alone with cut-away walls; "all" stacks every floor. */
export default function Model3D({ layout, level = "all" }: { layout: Layout; level?: number | "all" }) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const width = el.clientWidth;
    const height = 420;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf5f5f4);
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 500);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    el.appendChild(renderer.domElement);
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const sun = new THREE.DirectionalLight(0xffffff, 0.8);
    sun.position.set(20, 40, 10);
    scene.add(sun);

    // Layout x -> world x, layout y (from road) -> world z, height -> world y.
    const plot = layout.plot;
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(plot.w, plot.d), new THREE.MeshLambertMaterial({ color: 0xdde5d5 }));
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(plot.w / 2, -0.01, plot.d / 2);
    scene.add(ground);

    const wallMat = new THREE.MeshLambertMaterial({ color: 0xffffff });
    const shown = level === "all" ? layout.floors : layout.floors.filter((f) => f.level === level);
    for (const floor of shown) {
      const y0 = floor.level * STOREY;
      for (const r of floor.rooms) {
        const slab = new THREE.Mesh(
          new THREE.BoxGeometry(r.rect.w, 0.05, r.rect.d),
          new THREE.MeshLambertMaterial({ color: COLOURS[r.type] ?? 0xeeeeee }),
        );
        slab.position.set(r.rect.x + r.rect.w / 2, y0, r.rect.y + r.rect.d / 2);
        scene.add(slab);
        // Cut-away walls on the floor being looked at, full height below it.
        const top = level === "all" ? layout.floors.length - 1 : level;
        const h = floor.level === top ? 1.2 : STOREY;
        if (floor.level === top) {
          const tag = label(r.name);
          tag.position.set(r.rect.x + r.rect.w / 2, y0 + 1.8, r.rect.y + r.rect.d / 2);
          scene.add(tag);
        }
        const { x, y, w, d } = r.rect;
        for (const [cx, cz, sx, sz] of [
          [x + w / 2, y, w, WALL],
          [x + w / 2, y + d, w, WALL],
          [x, y + d / 2, WALL, d],
          [x + w, y + d / 2, WALL, d],
        ]) {
          const wall = new THREE.Mesh(new THREE.BoxGeometry(sx, h, sz), wallMat);
          wall.position.set(cx, y0 + h / 2, cz);
          scene.add(wall);
        }
      }
    }

    const fp = layout.floors[0].footprint;
    const centreY = level === "all" ? (layout.floors.length * STOREY) / 2 : level * STOREY;
    const centre = new THREE.Vector3(fp.x + fp.w / 2, centreY, fp.y + fp.d / 2);
    const dist = Math.max(fp.w, fp.d) * 1.3 + 4; // frame the building, not the whole plot
    camera.position.set(centre.x + dist * 0.7, centre.y + dist, centre.z - dist * 0.7);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(centre);
    controls.update();

    let frame = 0;
    const tick = () => {
      frame = requestAnimationFrame(tick);
      controls.update();
      renderer.render(scene, camera);
    };
    tick();
    return () => {
      cancelAnimationFrame(frame);
      controls.dispose();
      renderer.dispose();
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh) {
          o.geometry.dispose();
          (o.material as THREE.Material).dispose();
        } else if (o instanceof THREE.Sprite) {
          o.material.map?.dispose();
          o.material.dispose();
        }
      });
      el.removeChild(renderer.domElement);
    };
  }, [layout, level]);

  return (
    <div>
      <div ref={host} className="w-full overflow-hidden rounded-md border border-stone-200" />
      <p className="mt-1 text-xs text-stone-500">Display only, drag to orbit. The IFC file is the model of record.</p>
    </div>
  );
}
