// Interior studio types (mirror apps/api/archmind/design/interior.py) and room-local geometry.
// Positions: metres from the room's front-left corner (front = road side), item centre.
// rot 0 faces +y (back to the front wall), 90 faces -x, 180 faces -y, 270 faces +x.

export type Rot = 0 | 90 | 180 | 270;
export type Side = "front" | "rear" | "left" | "right";
export type Category = "furniture" | "fixture" | "decor" | "plant";

export type CatalogItem = {
  id: string;
  name: string;
  category: Category;
  kind: string;
  rooms: string[];
  w: number;
  d: number;
  h: number;
  shape: string;
  layer: "floor" | "rug" | "wall" | "top";
  place: string;
  colour: string;
  price: number;
  styles: string[];
  clear: number;
  elev: number;
  surface: boolean;
  seats: number;
};
export type Finish = { id: string; name: string; pattern: string; colour: string; rate_m2: number };
export type Theme = { id: string; name: string };
export type Catalog = {
  version: string;
  status: string;
  currency: string;
  source: string;
  items: CatalogItem[];
  wall_finishes: Finish[];
  floor_finishes: Finish[];
  themes: Theme[];
};

export type Placement = { uid: string; item_id: string; room_id: string; x: number; y: number; rot: Rot; colour?: string | null };
export type RoomFinish = {
  wall: string;
  wall_colour?: string | null;
  floor: string;
  feature_side?: Side | null;
  feature?: string | null;
};
export type Interior = { theme: string; rooms: Record<string, RoomFinish>; items: Placement[] };
export type OpeningInfo = { kind: "door" | "window"; side: Side; offset: number; width: number };
export type RoomInfo = { id: string; name: string; type: string; floor: number; x: number; y: number; w: number; d: number; openings: OpeningInfo[] };
export type FitIssue = { uid: string | null; room_id: string; rule: string; result: "warn" | "fail"; message: string };
export type CostLine = { group: string; description: string; qty: number; unit: string; rate: number; amount: number };
export type InteriorOut = {
  option_id: string;
  saved: boolean;
  revision: number;
  catalog_version: string;
  interior: Interior;
  rooms: RoomInfo[];
  issues: FitIssue[];
  cost: { currency: string; lines: CostLine[]; total: number; label: string; warnings: string[] };
  can_edit: boolean;
};

export const size = (it: CatalogItem, rot: Rot): [number, number] => (rot === 90 || rot === 270 ? [it.d, it.w] : [it.w, it.d]);

export function box(it: CatalogItem, p: { x: number; y: number; rot: Rot }): [number, number, number, number] {
  const [sw, sd] = size(it, p.rot);
  return [p.x - sw / 2, p.y - sd / 2, p.x + sw / 2, p.y + sd / 2];
}

export const allowedIn = (it: CatalogItem, roomType: string) => it.rooms.includes("any") || it.rooms.includes(roomType);

export const nextRot = (r: Rot): Rot => (((r + 90) % 360) as Rot);

export const CATEGORY_LABEL: Record<Category, string> = {
  furniture: "Furniture",
  fixture: "Fixtures",
  decor: "Decor",
  plant: "Plants",
};

/** Height of the surface a tabletop item stands on (the tallest surface item under its centre). */
export function standHeight(p: Placement, items: Placement[], byId: Map<string, CatalogItem>): number {
  let h = 0;
  for (const q of items) {
    if (q.uid === p.uid || q.room_id !== p.room_id) continue;
    const qi = byId.get(q.item_id);
    if (!qi?.surface) continue;
    const [x0, y0, x1, y1] = box(qi, q);
    if (p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1) h = Math.max(h, qi.h);
  }
  return h;
}

/** Snap a wall-hung item's back against the nearest wall, facing into the room. */
export function snapToWall(it: CatalogItem, x: number, y: number, room: RoomInfo): { x: number; y: number; rot: Rot } {
  const inset = 0.06;
  const dist: [Side, number][] = [
    ["front", y],
    ["rear", room.d - y],
    ["left", x],
    ["right", room.w - x],
  ];
  const side = dist.sort((a, b) => a[1] - b[1])[0][0];
  const rot: Rot = { front: 0, rear: 180, left: 270, right: 90 }[side] as Rot;
  const [sw, sd] = size(it, rot);
  if (side === "front") return { x, y: inset + sd / 2, rot };
  if (side === "rear") return { x, y: room.d - inset - sd / 2, rot };
  if (side === "left") return { x: inset + sw / 2, y, rot };
  return { x: room.w - inset - sw / 2, y, rot };
}
