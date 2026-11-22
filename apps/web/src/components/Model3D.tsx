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

export default function Model3D({ layout }: { layout: Layout }) {
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
    for (const floor of layout.floors) {
      const y0 = floor.level * STOREY;
      for (const r of floor.rooms) {
        const slab = new THREE.Mesh(
          new THREE.BoxGeometry(r.rect.w, 0.05, r.rect.d),
          new THREE.MeshLambertMaterial({ color: COLOURS[r.type] ?? 0xeeeeee }),
        );
        slab.position.set(r.rect.x + r.rect.w / 2, y0, r.rect.y + r.rect.d / 2);
        scene.add(slab);
        // Room outline walls (cut-away height on the top floor so rooms stay visible).
        const h = floor.level === layout.floors.length - 1 ? 1.2 : STOREY;
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
    const centre = new THREE.Vector3(fp.x + fp.w / 2, (layout.floors.length * STOREY) / 2, fp.y + fp.d / 2);
    camera.position.set(centre.x + 14, 16, centre.z - 14);
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
        }
      });
      el.removeChild(renderer.domElement);
    };
  }, [layout]);

  return (
    <div>
      <div ref={host} className="w-full overflow-hidden rounded-md border border-stone-200" />
      <p className="mt-1 text-xs text-stone-500">Display only, drag to orbit. The IFC file is the model of record.</p>
    </div>
  );
}
