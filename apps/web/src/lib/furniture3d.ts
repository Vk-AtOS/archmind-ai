// Low-poly 3D models for catalogue shapes, built from primitives (no model files to license).
// Local frame: origin at the footprint centre on the floor, width along x, depth along z,
// front facing +z. Concept-level look, sized exactly to the catalogue dimensions.
import * as THREE from "three";

import type { CatalogItem } from "@/lib/interior";

type M = THREE.Material;
const std = (color: string | number, o: Partial<THREE.MeshStandardMaterialParameters> = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.75, metalness: 0, ...o });

function add(g: THREE.Group, geo: THREE.BufferGeometry, m: M, x: number, y: number, z: number, ry = 0) {
  const mesh = new THREE.Mesh(geo, m);
  mesh.position.set(x, y, z);
  mesh.rotation.y = ry;
  mesh.castShadow = true;
  g.add(mesh);
  return mesh;
}
const boxAt = (g: THREE.Group, m: M, w: number, h: number, d: number, x: number, y: number, z: number) =>
  add(g, new THREE.BoxGeometry(w, h, d), m, x, y + h / 2, z);
const cyl = (g: THREE.Group, m: M, rt: number, rb: number, h: number, x: number, y: number, z: number, seg = 16) =>
  add(g, new THREE.CylinderGeometry(rt, rb, h, seg), m, x, y + h / 2, z);
function ball(g: THREE.Group, m: M, r: number, x: number, y: number, z: number, sx = 1, sy = 1, sz = 1) {
  const s = add(g, new THREE.SphereGeometry(r, 14, 10), m, x, y, z);
  s.scale.set(sx, sy, sz);
  return s;
}

function legs(g: THREE.Group, m: M, w: number, d: number, h: number, inset = 0.05, r = 0.025) {
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) cyl(g, m, r, r, h, sx * (w / 2 - inset), 0, sz * (d / 2 - inset), 8);
}

function lathe(profile: [number, number][], m: M, g: THREE.Group, y = 0) {
  const pts = profile.map(([r, h]) => new THREE.Vector2(r, h));
  return add(g, new THREE.LatheGeometry(pts, 20), m, 0, y, 0);
}

function canvasMat(drawFn: (c: CanvasRenderingContext2D, w: number, h: number) => void, w = 256, h = 192) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  drawFn(c.getContext("2d")!, w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshStandardMaterial({ map: t, roughness: 0.9 });
}

const LEAF = ["#2e7d32", "#388e3c", "#1b5e20", "#43a047", "#558b2f"];

function pot(g: THREE.Group, r: number, h: number, colour = "#d7ccc8") {
  cyl(g, std(colour), r, r * 0.78, h, 0, 0, 0, 18);
  cyl(g, std("#4e342e"), r * 0.92, r * 0.92, 0.02, 0, h - 0.03, 0, 18);
}

type Builder = (g: THREE.Group, it: CatalogItem, c: string) => void;

const B: Record<string, Builder> = {
  bed: (g, { w, d, h }, c) => {
    const wood = std(c);
    boxAt(g, wood, w, 0.3, d, 0, 0, 0);
    boxAt(g, std("#f5f5f0"), w - 0.08, 0.2, d - 0.12, 0, 0.3, 0.03);
    boxAt(g, wood, w, h, 0.08, 0, 0, -d / 2 + 0.04);
    boxAt(g, std("#8fa3b8"), w - 0.06, 0.06, d * 0.55, 0, 0.48, d * 0.2);
    for (const s of [-1, 1]) boxAt(g, std("#ffffff"), w * 0.36, 0.12, 0.35, (s * w) / 4.4, 0.5, -d / 2 + 0.3);
  },
  wardrobe: (g, { w, d, h }, c) => {
    boxAt(g, std(c), w, h, d, 0, 0, 0);
    const doors = Math.max(2, Math.round(w / 0.6));
    const dark = std("#3e2723");
    for (let i = 1; i < doors; i++) boxAt(g, dark, 0.01, h - 0.1, 0.01, -w / 2 + (i * w) / doors, 0.05, d / 2 + 0.005);
    for (let i = 0; i < doors; i++) boxAt(g, std("#b0bec5", { metalness: 0.8, roughness: 0.3 }), 0.02, 0.3, 0.02, -w / 2 + ((i + 0.5) * w) / doors + (i % 2 ? -0.2 : 0.2) * (w / doors), h * 0.45, d / 2 + 0.015);
  },
  sofa: (g, { w, d, h }, c) => {
    const m = std(c);
    boxAt(g, m, w, 0.42, d, 0, 0, 0);
    boxAt(g, m, w, h, 0.2, 0, 0, -d / 2 + 0.1);
    for (const s of [-1, 1]) boxAt(g, m, 0.18, 0.62, d, s * (w / 2 - 0.09), 0, 0);
    const cush = std(new THREE.Color(c).offsetHSL(0, 0, 0.06).getStyle());
    const n = Math.max(1, Math.round((w - 0.36) / 0.65));
    for (let i = 0; i < n; i++) boxAt(g, cush, (w - 0.36) / n - 0.02, 0.1, d - 0.25, -w / 2 + 0.18 + ((i + 0.5) * (w - 0.36)) / n, 0.42, 0.08);
  },
  sofa_l: (g, it, c) => {
    const m = std(c);
    const back = 0.9;
    B.sofa(g, { ...it, d: back }, c);
    g.children.forEach((o) => (o.position.z -= (it.d - back) / 2));
    boxAt(g, m, 0.9, 0.42, it.d - back, it.w / 2 - 0.45, 0, back / 2);
    boxAt(g, std(new THREE.Color(c).offsetHSL(0, 0, 0.06).getStyle()), 0.75, 0.1, it.d - back, it.w / 2 - 0.45, 0.42, back / 2);
  },
  armchair: (g, it, c) => B.sofa(g, it, c),
  table: (g, { w, d, h }, c) => {
    const m = std(c);
    boxAt(g, m, w, 0.04, d, 0, h - 0.04, 0);
    legs(g, m, w, d, h - 0.04);
  },
  glass_table: (g, { w, d, h }) => {
    boxAt(g, std("#b3e5fc", { transparent: true, opacity: 0.45, roughness: 0.05 }), w, 0.02, d, 0, h - 0.02, 0);
    legs(g, std("#9e9e9e", { metalness: 0.9, roughness: 0.3 }), w, d, h - 0.02, 0.08, 0.015);
  },
  tv_unit: (g, { w, d, h }, c) => {
    boxAt(g, std(c), w, h, d, 0, 0, 0);
    boxAt(g, std("#212121"), w * 0.03, 0.08, 0.15, 0, h, -d / 4);
    const tv = boxAt(g, std("#111111", { roughness: 0.2 }), w * 0.75, w * 0.42, 0.05, 0, h + 0.08, -d / 4);
    tv.position.y += 0.02;
  },
  sideboard: (g, { w, d, h }, c) => {
    boxAt(g, std(c), w, h - 0.12, d, 0, 0.12, 0);
    legs(g, std("#3e2723"), w, d, 0.12, 0.08, 0.02);
    for (let i = 1; i < 3; i++) boxAt(g, std("#3e2723"), 0.01, h - 0.2, 0.01, -w / 2 + (i * w) / 3, 0.16, d / 2 + 0.005);
  },
  dining_set: (g, { w, d, seats }, c) => {
    const m = std(c);
    const tw = w - 0.8;
    const td = d - 0.8;
    boxAt(g, m, tw, 0.04, td, 0, 0.71, 0);
    legs(g, m, tw, td, 0.71, 0.08, 0.03);
    const per = Math.max(1, seats / 2);
    for (const s of [-1, 1])
      for (let i = 0; i < per; i++) {
        const x = -tw / 2 + ((i + 0.5) * tw) / per;
        const z = s * (td / 2 + 0.2);
        boxAt(g, m, 0.42, 0.04, 0.42, x, 0.43, z);
        legs(g, m, 0.42, 0.42, 0.43, 0.03, 0.015);
        boxAt(g, m, 0.42, 0.45, 0.04, x, 0.47, z + s * 0.19);
      }
  },
  bookshelf: (g, { w, d, h }, c) => {
    const m = std(c);
    for (const s of [-1, 1]) boxAt(g, m, 0.03, h, d, s * (w / 2 - 0.015), 0, 0);
    for (let i = 0; i <= 5; i++) boxAt(g, m, w, 0.025, d, 0, (i * (h - 0.03)) / 5, 0);
    const bookCols = ["#c62828", "#1565c0", "#2e7d32", "#f9a825", "#6a1b9a", "#455a64"];
    for (let i = 0; i < 5; i++)
      for (let k = 0; k < 7; k++) boxAt(g, std(bookCols[(i + k) % 6]), 0.08, 0.22 + ((i * k) % 3) * 0.03, d * 0.75, -w / 2 + 0.1 + k * 0.1, 0.03 + (i * (h - 0.03)) / 5, 0);
  },
  pooja_unit: (g, { w, d, h }, c) => {
    const m = std(c);
    boxAt(g, m, w, h * 0.45, d, 0, 0, 0);
    for (const s of [-1, 1]) boxAt(g, m, 0.06, h * 0.45, d, s * (w / 2 - 0.03), h * 0.45, 0);
    boxAt(g, std("#f3e5ab"), w - 0.12, h * 0.45, 0.02, 0, h * 0.45, -d / 2 + 0.01);
    const arch = add(g, new THREE.CylinderGeometry(w / 2, w / 2, d, 20, 1, false, -Math.PI / 2, Math.PI), m, 0, h * 0.9, 0);
    arch.rotation.x = Math.PI / 2;
    arch.rotation.z = Math.PI / 2;
    const gold = std("#c9a227", { metalness: 0.8, roughness: 0.3 });
    ball(g, gold, 0.08, 0, h * 0.45 + 0.12, -0.05);
    ball(g, gold, 0.05, 0, h * 0.45 + 0.26, -0.05);
    cyl(g, std("#ff8f00", { emissive: "#ff6f00", emissiveIntensity: 0.6 }), 0.01, 0.02, 0.05, 0.2, h * 0.45, 0.1);
  },
  counter: (g, { w, d }, c) => {
    boxAt(g, std(c), w, 0.86, d, 0, 0, 0);
    boxAt(g, std("#37474f", { roughness: 0.3 }), w, 0.04, d + 0.02, 0, 0.86, 0);
    boxAt(g, std("#90a4ae", { metalness: 0.8, roughness: 0.25 }), 0.6, 0.02, 0.4, w / 2 - 0.5, 0.89, 0);
    boxAt(g, std("#111111"), 0.6, 0.015, 0.5, -w / 2 + 0.5, 0.9, 0);
    for (const [dx, dz] of [[-0.14, -0.12], [0.14, -0.12], [-0.14, 0.12], [0.14, 0.12]]) cyl(g, std("#424242"), 0.08, 0.08, 0.01, -w / 2 + 0.5 + dx, 0.915, dz);
    boxAt(g, std(c), w, 0.7, 0.35, 0, 1.5, -d / 2 + 0.175);
    for (let i = 1; i < Math.round(w / 0.6); i++) boxAt(g, std("#9e9e9e"), 0.01, 0.84, 0.01, -w / 2 + i * 0.6, 0.01, d / 2 + 0.005);
  },
  fridge: (g, { w, d, h }, c) => {
    boxAt(g, std(c, { metalness: 0.5, roughness: 0.35 }), w, h, d, 0, 0, 0);
    boxAt(g, std("#455a64"), w, 0.01, 0.01, 0, h * 0.62, d / 2 + 0.005);
    boxAt(g, std("#b0bec5", { metalness: 0.9 }), 0.02, 0.5, 0.03, w / 2 - 0.08, h * 0.7, d / 2 + 0.02);
  },
  wc: (g, { w, d }, c) => {
    const m = std(c, { roughness: 0.2 });
    const bowl = add(g, new THREE.CylinderGeometry(w / 2, w / 2.6, 0.38, 20), m, 0, 0.2, 0.05);
    bowl.scale.z = d / w / 1.2;
    boxAt(g, m, w * 0.9, 0.04, d * 0.75, 0, 0.4, 0.05);
    boxAt(g, std("#e0e0e0"), 0.2, 0.15, 0.02, 0, 0.9, -d / 2 + 0.01);
  },
  basin: (g, { w, d, h }) => {
    boxAt(g, std("#8d6e63"), w, h - 0.15, d, 0, 0, 0);
    boxAt(g, std("#fafafa", { roughness: 0.15 }), w, 0.15, d, 0, h - 0.15, 0);
    cyl(g, std("#b0bec5", { metalness: 0.9, roughness: 0.2 }), 0.015, 0.015, 0.2, 0, h, -d / 2 + 0.08, 8);
  },
  shower: (g, { w, d, h }) => {
    boxAt(g, std("#eceff1"), w, 0.06, d, 0, 0, 0);
    const glass = std("#b3e5fc", { transparent: true, opacity: 0.28, roughness: 0.05 });
    boxAt(g, glass, w, h, 0.01, 0, 0.06, d / 2);
    boxAt(g, glass, 0.01, h, d, w / 2, 0.06, 0);
    cyl(g, std("#b0bec5", { metalness: 0.9 }), 0.1, 0.1, 0.02, 0, h - 0.1, -d / 2 + 0.2);
  },
  buddha: (g, { w, h }, c) => {
    const m = std(c, { metalness: 0.6, roughness: 0.45 });
    cyl(g, m, w / 2, w / 2, h * 0.12, 0, 0, 0, 24);
    ball(g, m, w * 0.45, 0, h * 0.2, 0.02, 1, 0.42, 0.8); // crossed legs
    ball(g, m, w * 0.28, 0, h * 0.45, 0, 1, 1.35, 0.8); // torso
    ball(g, m, w * 0.17, 0, h * 0.78, 0.01); // head
    ball(g, m, w * 0.07, 0, h * 0.92, 0); // ushnisha
    for (const s of [-1, 1]) ball(g, m, w * 0.05, s * w * 0.15, h * 0.76, 0, 0.5, 1.6, 0.6); // ears
    ball(g, m, w * 0.12, 0, h * 0.27, w * 0.18, 1.6, 0.5, 1); // hands in lap
  },
  buddha_head: (g, { w, h }, c) => {
    const m = std(c, { metalness: 0.3, roughness: 0.6 });
    boxAt(g, std("#424242"), w, h * 0.2, w, 0, 0, 0);
    cyl(g, m, w * 0.18, w * 0.22, h * 0.2, 0, h * 0.2, 0);
    ball(g, m, w * 0.38, 0, h * 0.65, 0, 1, 1.15, 1);
    ball(g, m, w * 0.14, 0, h * 0.95, 0);
  },
  idol: (g, { w, h }, c) => {
    const m = std(c, { metalness: 0.85, roughness: 0.3 });
    cyl(g, m, w / 2, w / 2, h * 0.12, 0, 0, 0, 20);
    ball(g, m, w * 0.35, 0, h * 0.38, 0, 1, 1.1, 0.9);
    ball(g, m, w * 0.24, 0, h * 0.75, 0.02);
    for (const s of [-1, 1]) ball(g, m, w * 0.16, s * w * 0.24, h * 0.76, 0, 0.4, 1, 0.9);
    const trunk = add(g, new THREE.CylinderGeometry(0.012, 0.025, h * 0.32, 8), m, w * 0.04, h * 0.55, w * 0.18);
    trunk.rotation.z = 0.35;
    add(g, new THREE.ConeGeometry(w * 0.12, h * 0.15, 12), m, 0, h * 0.95, 0.01);
  },
  urli: (g, { w, h }, c) => {
    lathe([[0.02, 0], [w * 0.3, 0.005], [w * 0.47, h * 0.6], [w / 2, h]], std(c, { metalness: 0.85, roughness: 0.3, side: THREE.DoubleSide }), g);
    cyl(g, std("#4fc3f7", { transparent: true, opacity: 0.7 }), w * 0.46, w * 0.46, 0.005, 0, h * 0.7, 0, 24);
    const cols = ["#ff7043", "#ffca28", "#e91e63", "#ffffff"];
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2;
      ball(g, std(cols[i % 4]), 0.035, Math.cos(a) * w * 0.25 * (i % 2 ? 1 : 0.5), h * 0.75, Math.sin(a) * w * 0.25 * (i % 2 ? 1 : 0.5), 1, 0.5, 1);
    }
  },
  vase_tall: (g, { w, h }, c) => {
    lathe([[0, 0], [w * 0.35, 0.02], [w / 2, h * 0.3], [w * 0.2, h * 0.55], [w * 0.25, h * 0.6]], std(c, { roughness: 0.4 }), g);
    for (let i = 0; i < 6; i++) {
      const s = add(g, new THREE.CylinderGeometry(0.004, 0.004, h * 0.5, 4), std("#8d6e63"), (i - 2.5) * 0.02, h * 0.82, ((i % 3) - 1) * 0.02);
      s.rotation.z = (i - 2.5) * 0.08;
      ball(g, std("#d7b98e"), 0.035, (i - 2.5) * 0.045, h * 1.02, ((i % 3) - 1) * 0.03, 0.6, 1.4, 0.6);
    }
  },
  vase: (g, { w, h }, c) => {
    lathe([[0, 0], [w * 0.4, 0.01], [w / 2, h * 0.45], [w * 0.22, h * 0.85], [w * 0.28, h]], std(c, { roughness: 0.3 }), g);
  },
  lamp: (g, { w, h }, c) => {
    const metal = std("#212121", { metalness: 0.7, roughness: 0.4 });
    cyl(g, metal, w * 0.35, w * 0.4, 0.03, 0, 0, 0, 20);
    cyl(g, metal, 0.012, 0.012, h * 0.75, 0, 0.03, 0, 8);
    cyl(g, std(c, { emissive: "#ffe0a3", emissiveIntensity: 0.5, side: THREE.DoubleSide }), w * 0.25, w * 0.45, h * 0.25, 0, h * 0.75, 0, 20);
  },
  wall_art: (g, { w, d, h }, c) => {
    boxAt(g, std("#212121"), w, h, d, 0, 0, 0);
    const art = canvasMat((x, cw, ch) => {
      x.fillStyle = "#f5f0e6";
      x.fillRect(0, 0, cw, ch);
      const cols = [c, "#3d5a80", "#e0c068", "#98c1d9", "#293241"];
      for (let i = 0; i < 7; i++) {
        x.fillStyle = cols[i % cols.length];
        x.globalAlpha = 0.85;
        x.beginPath();
        x.arc(((i * 53) % cw) + 20, ((i * 71) % ch) + 20, 18 + ((i * 13) % 40), 0, Math.PI * 2);
        x.fill();
      }
    });
    add(g, new THREE.PlaneGeometry(w - 0.06, h - 0.06), art, 0, h / 2, d / 2 + 0.002);
  },
  wall_art_folk: (g, { w, d, h }, c) => {
    boxAt(g, std("#5d4037"), w, h, d, 0, 0, 0);
    const art = canvasMat((x, cw, ch) => {
      x.fillStyle = "#f7e7b4";
      x.fillRect(0, 0, cw, ch);
      x.strokeStyle = c;
      x.lineWidth = 8;
      x.strokeRect(6, 6, cw - 12, ch - 12);
      x.strokeStyle = "#1b5e20";
      x.lineWidth = 3;
      for (let i = 14; i < cw - 14; i += 10) {
        x.beginPath();
        x.moveTo(i, 14);
        x.lineTo(i + 5, 22);
        x.stroke();
      }
      for (const [fx, fy, col] of [[cw * 0.33, ch * 0.5, "#d84315"], [cw * 0.66, ch * 0.5, "#1565c0"]] as const) {
        x.fillStyle = col;
        x.beginPath();
        x.ellipse(fx, fy, 38, 18, 0, 0, Math.PI * 2);
        x.fill();
        x.beginPath();
        x.moveTo(fx + 34, fy);
        x.lineTo(fx + 58, fy - 16);
        x.lineTo(fx + 58, fy + 16);
        x.fill();
        x.fillStyle = "#fff";
        x.beginPath();
        x.arc(fx - 22, fy - 4, 4, 0, Math.PI * 2);
        x.fill();
      }
    });
    add(g, new THREE.PlaneGeometry(w - 0.08, h - 0.08), art, 0, h / 2, d / 2 + 0.002);
  },
  mirror: (g, { w, d }, c) => {
    const frame = add(g, new THREE.CylinderGeometry(w / 2, w / 2, d, 32), std(c, { metalness: 0.85, roughness: 0.3 }), 0, w / 2, 0);
    frame.rotation.x = Math.PI / 2;
    const glass = add(g, new THREE.CircleGeometry(w / 2 - 0.05, 32), std("#dfe7ea", { metalness: 1, roughness: 0.05 }), 0, w / 2, d / 2 + 0.002);
    glass.rotation.set(0, 0, 0);
  },
  clock: (g, { w, d }, c) => {
    const face = add(g, new THREE.CylinderGeometry(w / 2, w / 2, d, 32), std("#fafafa"), 0, w / 2, 0);
    face.rotation.x = Math.PI / 2;
    const rim = add(g, new THREE.TorusGeometry(w / 2, 0.015, 8, 32), std(c), 0, w / 2, d / 2);
    rim.rotation.set(0, 0, 0);
    boxAt(g, std("#111"), 0.012, w * 0.3, 0.005, 0, w / 2, d / 2 + 0.005);
    const m = boxAt(g, std("#111"), 0.012, w * 0.22, 0.005, 0.05, w / 2 - 0.02, d / 2 + 0.006);
    m.rotation.z = -1.2;
  },
  rug: (g, { w, d }, c) => {
    boxAt(g, std(c, { roughness: 1 }), w, 0.012, d, 0, 0, 0);
    boxAt(g, std(new THREE.Color(c).offsetHSL(0, 0, -0.12).getStyle(), { roughness: 1 }), w - 0.2, 0.013, d - 0.2, 0, 0, 0);
    boxAt(g, std(c, { roughness: 1 }), w - 0.3, 0.014, d - 0.3, 0, 0, 0);
  },
  rug_pattern: (g, { w, d }, c) => {
    const m = canvasMat((x, cw, ch) => {
      x.fillStyle = c;
      x.fillRect(0, 0, cw, ch);
      const stripes = ["#f3e0b5", "#1e3a5f", "#f3e0b5", "#2e7d32"];
      for (let i = 0; i < 12; i++) {
        x.fillStyle = stripes[i % 4];
        x.fillRect(0, (i * ch) / 12 + ch / 30, cw, ch / 40);
      }
      x.fillStyle = "#f3e0b5";
      for (let i = 0; i < 8; i++) {
        x.beginPath();
        x.moveTo((i * cw) / 8, ch / 2);
        x.lineTo((i * cw) / 8 + cw / 16, ch / 2 - 14);
        x.lineTo((i * cw) / 8 + cw / 8, ch / 2);
        x.lineTo((i * cw) / 8 + cw / 16, ch / 2 + 14);
        x.fill();
      }
    });
    const top = add(g, new THREE.PlaneGeometry(w, d), m, 0, 0.012, 0);
    top.rotation.x = -Math.PI / 2;
  },
  plant_broad: (g, { w, h }) => {
    pot(g, w * 0.3, h * 0.28);
    cyl(g, std("#5d4037"), 0.015, 0.02, h * 0.45, 0, h * 0.28, 0, 6);
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2;
      const r = w * (0.18 + (i % 3) * 0.07);
      const leaf = ball(g, std(LEAF[i % LEAF.length], { side: THREE.DoubleSide }), w * 0.2, Math.cos(a) * r, h * (0.5 + (i % 4) * 0.12), Math.sin(a) * r, 1, 0.25, 0.7);
      leaf.rotation.set(0.4, a, 0.3);
    }
  },
  plant_palm: (g, { w, h }) => {
    pot(g, w * 0.25, h * 0.2, "#a1887f");
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2;
      const frond = add(g, new THREE.ConeGeometry(0.06, h * 0.55, 4), std(LEAF[i % LEAF.length]), Math.cos(a) * w * 0.2, h * 0.55 + (i % 3) * 0.08, Math.sin(a) * w * 0.2);
      frond.rotation.set(Math.sin(a) * 0.6, 0, -Math.cos(a) * 0.6);
      frond.scale.set(1, 1, 0.2);
    }
  },
  plant_snake: (g, { w, h }) => {
    pot(g, w * 0.4, h * 0.3, "#eeeeee");
    for (let i = 0; i < 8; i++) {
      const blade = boxAt(g, std(i % 2 ? "#558b2f" : "#9ccc65"), 0.05, h * (0.45 + (i % 3) * 0.1), 0.012, ((i % 4) - 1.5) * 0.05, h * 0.28, (Math.floor(i / 4) - 0.5) * 0.06);
      blade.rotation.z = ((i % 4) - 1.5) * 0.08;
    }
  },
  plant_bush: (g, { w, h }, c) => {
    pot(g, w * 0.38, h * 0.4, c === "#43a047" ? "#c9a227" : "#d7ccc8");
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      ball(g, std(LEAF[i % LEAF.length]), w * 0.16, Math.cos(a) * w * 0.18, h * (0.55 + (i % 3) * 0.12), Math.sin(a) * w * 0.18);
    }
  },
  plant_hanging: (g, { w, h }) => {
    cyl(g, std("#bdbdbd", { metalness: 0.6 }), 0.005, 0.005, 0.25, 0, h, 0, 4);
    pot(g, w * 0.4, 0.18, "#e0e0e0");
    g.children.slice(-2).forEach((o) => (o.position.y += h - 0.18));
    for (let i = 0; i < 14; i++) {
      const a = (i / 14) * Math.PI * 2;
      ball(g, std(LEAF[i % LEAF.length]), 0.04, Math.cos(a) * w * 0.38, h - 0.02 - (i % 5) * 0.09, Math.sin(a) * w * 0.38 * 0.5, 1, 0.5, 1);
    }
  },
  green_wall: (g, { w, d, h }) => {
    boxAt(g, std("#4e342e"), w, h, d * 0.3, 0, 0, -d * 0.35);
    for (let i = 0; i < 90; i++) {
      const x = -w / 2 + 0.07 + ((i * 37) % 100) / 100 * (w - 0.14);
      const y = 0.07 + ((i * 61) % 100) / 100 * (h - 0.14);
      ball(g, std(LEAF[i % LEAF.length]), 0.07 + (i % 3) * 0.02, x, y, 0, 1, 1, 0.6);
    }
  },
};

/** Build an item model. colour overrides the catalogue colour for the main material. */
export function buildItem(it: CatalogItem, colour?: string | null): THREE.Group {
  const g = new THREE.Group();
  (B[it.shape] ?? ((gg, i, c) => boxAt(gg, std(c), i.w, i.h, i.d, 0, 0, 0)))(g, it, colour || it.colour);
  return g;
}
