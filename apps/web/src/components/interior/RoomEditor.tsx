"use client";

// Top-down room editor (ARCH-156): drag items, R to rotate, Delete to remove, arrows to nudge.
// Plan orientation matches the drawings: the front (road side) wall is at the bottom.
import { useRef } from "react";

import { box, type CatalogItem, type Category, type FitIssue, type Placement, type RoomInfo, snapToWall } from "@/lib/interior";

const FILL: Record<Category, string> = { furniture: "#e7d3bd", fixture: "#cfe0ea", decor: "#e6d3ee", plant: "#cfe8c9" };
const STROKE: Record<Category, string> = { furniture: "#8d6e63", fixture: "#546e7a", decor: "#7b1fa2", plant: "#2e7d32" };
const PAD = 24;
const SNAP = 0.05;

type Props = {
  room: RoomInfo;
  items: Placement[];
  byId: Map<string, CatalogItem>;
  issues: FitIssue[];
  selected: string | null;
  editable: boolean;
  onSelect: (uid: string | null) => void;
  onMove: (uid: string, patch: Partial<Placement>) => void;
  onRotate: (uid: string) => void;
  onDelete: (uid: string) => void;
};

export default function RoomEditor({ room, items, byId, issues, selected, editable, onSelect, onMove, onRotate, onDelete }: Props) {
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ uid: string; dx: number; dy: number } | null>(null);
  const s = Math.min(560 / room.w, 460 / room.d);
  const W = room.w * s + 2 * PAD;
  const H = room.d * s + 2 * PAD;
  const X = (x: number) => PAD + x * s;
  const Y = (y: number) => PAD + (room.d - y) * s;
  const worst = (uid: string) => {
    const r = issues.filter((i) => i.uid === uid).map((i) => i.result);
    return r.includes("fail") ? "fail" : r.includes("warn") ? "warn" : null;
  };

  function toRoom(e: React.PointerEvent): [number, number] {
    const pt = svg.current!.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const p = pt.matrixTransform(svg.current!.getScreenCTM()!.inverse());
    return [(p.x - PAD) / s, room.d - (p.y - PAD) / s];
  }
  const snap = (v: number) => Math.round(v / SNAP) * SNAP;

  function down(e: React.PointerEvent, p: Placement) {
    e.stopPropagation();
    onSelect(p.uid);
    if (!editable) return;
    const [x, y] = toRoom(e);
    drag.current = { uid: p.uid, dx: p.x - x, dy: p.y - y };
    (e.target as Element).setPointerCapture(e.pointerId);
  }
  function move(e: React.PointerEvent) {
    const d = drag.current;
    if (!d) return;
    const [x, y] = toRoom(e);
    const nx = snap(x + d.dx);
    const ny = snap(y + d.dy);
    const p = items.find((i) => i.uid === d.uid);
    const it = p && byId.get(p.item_id);
    if (!p || !it) return;
    if (nx === p.x && ny === p.y) return;
    onMove(p.uid, it.layer === "wall" ? snapToWall(it, nx, ny, room) : { x: nx, y: ny });
  }
  function key(e: React.KeyboardEvent) {
    if (!editable || !selected) return;
    const p = items.find((i) => i.uid === selected);
    if (!p) return;
    const step = e.shiftKey ? 0.25 : SNAP;
    const nudge: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
    if (e.key === "r" || e.key === "R") onRotate(p.uid);
    else if (e.key === "Delete" || e.key === "Backspace") onDelete(p.uid);
    else if (nudge[e.key]) onMove(p.uid, { x: +(p.x + nudge[e.key][0]).toFixed(3), y: +(p.y + nudge[e.key][1]).toFixed(3) });
    else return;
    e.preventDefault();
  }

  const order = { rug: 0, floor: 1, top: 2, wall: 3 } as const;
  const sorted = [...items].sort((a, b) => order[byId.get(a.item_id)?.layer ?? "floor"] - order[byId.get(b.item_id)?.layer ?? "floor"]);

  return (
    <svg
      ref={svg}
      viewBox={`0 0 ${W} ${H}`}
      className="w-full touch-none select-none rounded-md border border-stone-200 bg-white outline-none focus:ring-2 focus:ring-amber-400"
      tabIndex={0}
      onKeyDown={key}
      onPointerMove={move}
      onPointerUp={() => (drag.current = null)}
      onPointerDown={() => onSelect(null)}
      data-testid="room-editor"
      aria-label={`${room.name} plan editor`}
    >
      <rect x={X(0)} y={Y(room.d)} width={room.w * s} height={room.d * s} fill="#faf8f4" stroke="#222" strokeWidth={4} />
      {room.openings.map((o, i) => {
        const a = o.offset - o.width / 2;
        const b = o.offset + o.width / 2;
        const [x1, y1, x2, y2] =
          o.side === "front" ? [a, 0, b, 0] : o.side === "rear" ? [a, room.d, b, room.d] : o.side === "left" ? [0, a, 0, b] : [room.w, a, room.w, b];
        const zone =
          o.side === "front"
            ? [a, 0, b, o.width]
            : o.side === "rear"
              ? [a, room.d - o.width, b, room.d]
              : o.side === "left"
                ? [0, a, o.width, b]
                : [room.w - o.width, a, room.w, b];
        return (
          <g key={i}>
            {o.kind === "door" && (
              <rect x={X(zone[0])} y={Y(zone[3])} width={(zone[2] - zone[0]) * s} height={(zone[3] - zone[1]) * s} fill="none" stroke="#c0392b" strokeDasharray="4 3" opacity={0.6} />
            )}
            <line x1={X(x1)} y1={Y(y1)} x2={X(x2)} y2={Y(y2)} stroke={o.kind === "door" ? "#c0392b" : "#2e86c1"} strokeWidth={6} />
          </g>
        );
      })}
      {sorted.map((p) => {
        const it = byId.get(p.item_id);
        if (!it) return null;
        const [x0, y0, x1, y1] = box(it, p);
        const bad = worst(p.uid);
        const sel = p.uid === selected;
        const cx = X(p.x);
        const cy = Y(p.y);
        // front edge marker shows which way the item faces
        const f = { 0: [x0, y1, x1, y1], 90: [x0, y0, x0, y1], 180: [x0, y0, x1, y0], 270: [x1, y0, x1, y1] }[p.rot];
        const label = it.name.split(",")[0];
        const fs = Math.max(8, Math.min(12, ((x1 - x0) * s) / (0.6 * label.length)));
        return (
          <g key={p.uid} onPointerDown={(e) => down(e, p)} className={editable ? "cursor-move" : "cursor-pointer"} data-testid="placed-item" data-item={it.id}>
            <rect
              x={X(x0)}
              y={Y(y1)}
              width={(x1 - x0) * s}
              height={(y1 - y0) * s}
              rx={it.layer === "top" || it.category === "plant" ? 6 : 2}
              fill={p.colour && it.layer !== "rug" ? p.colour : FILL[it.category]}
              fillOpacity={it.layer === "rug" ? 0.35 : 0.9}
              stroke={sel ? "#f59e0b" : bad === "fail" ? "#dc2626" : bad === "warn" ? "#d97706" : STROKE[it.category]}
              strokeWidth={sel ? 3 : bad ? 2.5 : 1.2}
              strokeDasharray={it.layer === "wall" ? "3 2" : undefined}
            />
            <line x1={X(f[0])} y1={Y(f[1])} x2={X(f[2])} y2={Y(f[3])} stroke="#111" strokeWidth={2.5} opacity={0.55} />
            {it.layer !== "top" && (
              <text x={cx} y={cy + fs / 3} fontSize={fs} textAnchor="middle" fill="#292524" pointerEvents="none">
                {label}
              </text>
            )}
          </g>
        );
      })}
      <text x={W / 2} y={H - 6} fontSize={10} textAnchor="middle" fill="#78716c">
        FRONT (road side)
      </text>
    </svg>
  );
}
