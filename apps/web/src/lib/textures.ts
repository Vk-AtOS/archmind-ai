// Procedural wall and floor textures drawn on a canvas (no image assets to license or host).
// Each texture covers TILE metres; callers set repeat = surface size / TILE.
import * as THREE from "three";

export const TILE = 1.2;
const PX = 256;

function shade(hex: string, f: number): string {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(v * f))));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

// Deterministic noise so the same finish always looks the same.
function rng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function speckle(g: CanvasRenderingContext2D, base: string, amount: number, seed: number) {
  const r = rng(seed);
  for (let i = 0; i < 1400; i++) {
    g.fillStyle = shade(base, 1 + (r() - 0.5) * amount);
    g.fillRect(r() * PX, r() * PX, 2 + r() * 3, 2 + r() * 3);
  }
}

const draw: Record<string, (g: CanvasRenderingContext2D, c: string) => void> = {
  paint: (g, c) => {
    g.fillStyle = c;
    g.fillRect(0, 0, PX, PX);
    speckle(g, c, 0.04, 3);
  },
  plaster: (g, c) => {
    g.fillStyle = c;
    g.fillRect(0, 0, PX, PX);
    const r = rng(7);
    for (let i = 0; i < 90; i++) {
      g.fillStyle = shade(c, 0.92 + r() * 0.14);
      g.globalAlpha = 0.35;
      g.beginPath();
      g.ellipse(r() * PX, r() * PX, 10 + r() * 30, 6 + r() * 18, r() * 3, 0, Math.PI * 2);
      g.fill();
    }
    g.globalAlpha = 1;
  },
  brick: (g, c) => {
    g.fillStyle = "#d6cfc4";
    g.fillRect(0, 0, PX, PX);
    const rows = 16;
    const bh = PX / rows;
    const bw = bh * 3.2;
    const r = rng(11);
    for (let row = 0; row < rows; row++) {
      const off = row % 2 ? bw / 2 : 0;
      for (let x = -bw; x < PX + bw; x += bw) {
        g.fillStyle = shade(c, 0.8 + r() * 0.35);
        g.fillRect(x + off + 1.5, row * bh + 1.5, bw - 3, bh - 3);
      }
    }
  },
  wood: (g, c) => {
    const planks = 6;
    const pw = PX / planks;
    const r = rng(5);
    for (let i = 0; i < planks; i++) {
      g.fillStyle = shade(c, 0.85 + r() * 0.25);
      g.fillRect(i * pw, 0, pw, PX);
      g.strokeStyle = shade(c, 0.7);
      g.globalAlpha = 0.35;
      for (let k = 0; k < 6; k++) {
        g.beginPath();
        const x = i * pw + r() * pw;
        g.moveTo(x, 0);
        g.bezierCurveTo(x + 6, PX / 3, x - 6, (2 * PX) / 3, x + 3, PX);
        g.stroke();
      }
      g.globalAlpha = 1;
      g.fillStyle = shade(c, 0.55);
      g.fillRect(i * pw, 0, 1.5, PX);
      g.fillRect(i * pw, r() * PX, pw, 1.5);
    }
  },
  herringbone: (g, c) => {
    g.fillStyle = shade(c, 0.6);
    g.fillRect(0, 0, PX, PX);
    const r = rng(9);
    const L = 64;
    const W = 16;
    g.save();
    for (let y = -PX; y < 2 * PX; y += W * 2) {
      for (let x = -PX; x < 2 * PX; x += L) {
        for (const dir of [1, -1]) {
          g.save();
          g.translate(x + (dir > 0 ? 0 : L / 2), y);
          g.rotate((dir * Math.PI) / 4);
          g.fillStyle = shade(c, 0.85 + r() * 0.25);
          g.fillRect(0, 0, L - 2, W - 2);
          g.restore();
        }
      }
    }
    g.restore();
  },
  stone: (g, c) => {
    g.fillStyle = shade(c, 0.6);
    g.fillRect(0, 0, PX, PX);
    const r = rng(13);
    let y = 0;
    while (y < PX) {
      const h = 28 + r() * 30;
      let x = -r() * 40;
      while (x < PX) {
        const w = 40 + r() * 60;
        g.fillStyle = shade(c, 0.8 + r() * 0.35);
        g.fillRect(x + 2, y + 2, w - 4, h - 4);
        x += w;
      }
      y += h;
    }
  },
  geometric: (g, c) => {
    g.fillStyle = c;
    g.fillRect(0, 0, PX, PX);
    g.strokeStyle = shade(c, 0.65);
    g.lineWidth = 3;
    const s = PX / 4;
    for (let x = 0; x <= PX; x += s)
      for (let y = 0; y <= PX; y += s) {
        g.beginPath();
        g.moveTo(x, y - s / 2);
        g.lineTo(x + s / 2, y);
        g.lineTo(x, y + s / 2);
        g.lineTo(x - s / 2, y);
        g.closePath();
        g.stroke();
      }
  },
  floral: (g, c) => {
    g.fillStyle = c;
    g.fillRect(0, 0, PX, PX);
    const s = PX / 4;
    for (let i = 0; i < 4; i++)
      for (let j = 0; j < 4; j++) {
        const cx = i * s + (j % 2 ? s / 2 : 0) + s / 4;
        const cy = j * s + s / 2;
        g.fillStyle = shade(c, 0.75);
        for (let k = 0; k < 5; k++) {
          const a = (k / 5) * Math.PI * 2;
          g.beginPath();
          g.ellipse(cx + Math.cos(a) * 9, cy + Math.sin(a) * 9, 7, 4, a, 0, Math.PI * 2);
          g.fill();
        }
        g.fillStyle = "#c9a227";
        g.beginPath();
        g.arc(cx, cy, 4, 0, Math.PI * 2);
        g.fill();
      }
  },
  concrete: (g, c) => {
    g.fillStyle = c;
    g.fillRect(0, 0, PX, PX);
    speckle(g, c, 0.18, 17);
    g.fillStyle = shade(c, 0.75);
    g.fillRect(0, PX / 2, PX, 1.5);
    for (const [x, y] of [
      [40, 40],
      [200, 40],
      [40, 170],
      [200, 170],
    ]) {
      g.beginPath();
      g.arc(x, y, 3, 0, Math.PI * 2);
      g.fill();
    }
  },
  tile: (g, c) => grid(g, c, 2, 0.12),
  tile_small: (g, c) => grid(g, c, 8, 0.1),
  tile_terracotta: (g, c) => grid(g, c, 4, 0.25),
  marble: (g, c) => {
    g.fillStyle = c;
    g.fillRect(0, 0, PX, PX);
    const r = rng(21);
    g.strokeStyle = "rgba(120,120,130,0.35)";
    for (let k = 0; k < 7; k++) {
      g.lineWidth = 0.6 + r() * 1.6;
      g.beginPath();
      let x = r() * PX;
      let y = 0;
      g.moveTo(x, y);
      while (y < PX) {
        x += (r() - 0.5) * 40;
        y += 12 + r() * 20;
        g.lineTo(x, y);
      }
      g.stroke();
    }
    g.fillStyle = "rgba(160,160,160,0.6)";
    g.fillRect(0, 0, PX, 1);
    g.fillRect(0, 0, 1, PX);
  },
};

function grid(g: CanvasRenderingContext2D, c: string, n: number, vary: number) {
  const s = PX / n;
  const r = rng(n * 31);
  g.fillStyle = "#bdb6ac";
  g.fillRect(0, 0, PX, PX);
  for (let i = 0; i < n; i++)
    for (let j = 0; j < n; j++) {
      g.fillStyle = shade(c, 1 - vary / 2 + r() * vary);
      g.fillRect(i * s + 1.5, j * s + 1.5, s - 3, s - 3);
    }
}

const cache = new Map<string, THREE.CanvasTexture>();

/** Texture for a finish pattern in a colour; cached, so callers clone() before changing repeat. */
export function finishTexture(pattern: string, colour: string): THREE.CanvasTexture {
  const key = `${pattern}:${colour}`;
  let t = cache.get(key);
  if (!t) {
    const c = document.createElement("canvas");
    c.width = c.height = PX;
    (draw[pattern] ?? draw.paint)(c.getContext("2d")!, colour);
    t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.colorSpace = THREE.SRGBColorSpace;
    cache.set(key, t);
  }
  return t;
}

/** Small swatch image (data URL) for pickers. */
export function swatch(pattern: string, colour: string): string {
  return (finishTexture(pattern, colour).image as HTMLCanvasElement).toDataURL("image/png");
}
