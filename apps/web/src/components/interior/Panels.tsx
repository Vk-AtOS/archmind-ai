"use client";

import { useMemo, useState } from "react";

import {
  allowedIn,
  type Catalog,
  CATEGORY_LABEL,
  type CatalogItem,
  type Category,
  type Finish,
  type Placement,
  type RoomFinish,
  type RoomInfo,
  type Side,
} from "@/lib/interior";
import { swatch } from "@/lib/textures";
import { lenU, useUnit } from "@/lib/units";

const inr = (v: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(v);

export function SelectedItem({
  p,
  catalog,
  room,
  onSwap,
  onColour,
  onRotate,
  onDuplicate,
  onDelete,
  editable,
}: {
  p: Placement;
  catalog: Catalog;
  room: RoomInfo;
  onSwap: (itemId: string) => void;
  onColour: (c: string | null) => void;
  onRotate: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  editable: boolean;
}) {
  const unit = useUnit();
  const it = catalog.items.find((i) => i.id === p.item_id)!;
  // Swap among items that do the same job (same kind) or, for decor and plants, the same category.
  const swaps = catalog.items.filter(
    (i) => allowedIn(i, room.type) && i.layer === it.layer && (i.kind === it.kind || (it.category !== "furniture" && it.category !== "fixture" && i.category === it.category)),
  );
  return (
    <section className="card" data-testid="selected-item">
      <h3 className="mb-1 font-medium">{it.name}</h3>
      <p className="mb-3 text-xs text-stone-500">
        {lenU(it.w, unit)} × {lenU(it.d, unit)} × {lenU(it.h, unit)} high · {inr(it.price)} · {CATEGORY_LABEL[it.category]}
      </p>
      {editable && (
        <>
          <label className="label" htmlFor="swap">
            Swap for
          </label>
          <select id="swap" className="input mb-3" value={it.id} onChange={(e) => onSwap(e.target.value)}>
            {swaps.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name} · {inr(i.price)}
              </option>
            ))}
          </select>
          <div className="mb-3 flex items-center gap-2">
            <label className="label mb-0" htmlFor="item-colour">
              Colour
            </label>
            <input id="item-colour" type="color" value={p.colour || it.colour} onChange={(e) => onColour(e.target.value)} className="h-8 w-12 cursor-pointer rounded border border-stone-300" />
            {p.colour && (
              <button className="text-xs text-stone-500 underline" onClick={() => onColour(null)}>
                Reset
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="btn-secondary" onClick={onRotate} title="R">
              Rotate 90°
            </button>
            <button className="btn-secondary" onClick={onDuplicate}>
              Duplicate
            </button>
            <button className="btn-secondary text-red-700" onClick={onDelete} title="Delete">
              Remove
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export function AddItems({ catalog, room, onAdd }: { catalog: Catalog; room: RoomInfo; onAdd: (it: CatalogItem) => void }) {
  const unit = useUnit();
  const [tab, setTab] = useState<Category>("furniture");
  const [q, setQ] = useState("");
  const list = useMemo(
    () => catalog.items.filter((i) => i.category === tab && allowedIn(i, room.type) && i.name.toLowerCase().includes(q.toLowerCase())),
    [catalog, tab, room.type, q],
  );
  return (
    <section className="card">
      <h3 className="mb-2 font-medium">Add to {room.name}</h3>
      <div className="mb-2 flex flex-wrap gap-1" role="tablist">
        {(Object.keys(CATEGORY_LABEL) as Category[]).map((c) => (
          <button key={c} role="tab" aria-selected={tab === c} className={tab === c ? "btn" : "btn-secondary"} onClick={() => setTab(c)}>
            {CATEGORY_LABEL[c]}
          </button>
        ))}
      </div>
      <input className="input mb-2" placeholder="Search, e.g. Buddha, palm, sofa" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search catalogue" />
      <ul className="max-h-72 overflow-auto text-sm" data-testid="catalogue">
        {list.length === 0 && <li className="py-2 text-stone-500">Nothing in this category suits a {room.type}.</li>}
        {list.map((i) => (
          <li key={i.id} className="flex items-center justify-between gap-2 border-b border-stone-100 py-1.5">
            <span className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-sm border border-stone-300" style={{ background: i.colour }} />
              <span>
                {i.name}
                <span className="block text-xs text-stone-500">
                  {lenU(i.w, unit)} × {lenU(i.d, unit)} · {inr(i.price)}
                </span>
              </span>
            </span>
            <button className="btn-secondary" onClick={() => onAdd(i)} aria-label={`Add ${i.name}`}>
              Add
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Swatches({ list, value, onPick, colour, name }: { list: Finish[]; value: string; onPick: (id: string) => void; colour?: string | null; name: string }) {
  return (
    <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label={name}>
      {list.map((f) => (
        <button
          key={f.id}
          role="radio"
          aria-checked={value === f.id}
          aria-label={f.name}
          title={`${f.name} · ₹${f.rate_m2}/m²`}
          onClick={() => onPick(f.id)}
          className={`overflow-hidden rounded border-2 text-left ${value === f.id ? "border-amber-500" : "border-transparent"}`}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- generated data URL */}
          <img src={swatch(f.pattern, value === f.id && colour ? colour : f.colour)} alt="" className="h-10 w-full object-cover" />
          <span className="block truncate px-0.5 text-[10px] leading-tight text-stone-600">{f.name}</span>
        </button>
      ))}
    </div>
  );
}

export function Finishes({
  catalog,
  room,
  finish,
  editable,
  onChange,
  onApplyAll,
}: {
  catalog: Catalog;
  room: RoomInfo;
  finish: RoomFinish;
  editable: boolean;
  onChange: (patch: Partial<RoomFinish>) => void;
  onApplyAll: () => void;
}) {
  const wall = catalog.wall_finishes.find((f) => f.id === finish.wall);
  return (
    <section className={`card ${editable ? "" : "pointer-events-none opacity-80"}`} data-testid="finishes">
      <h3 className="mb-2 font-medium">Walls of {room.name}</h3>
      <Swatches name="Wall finish" list={catalog.wall_finishes} value={finish.wall} colour={finish.wall_colour} onPick={(id) => onChange({ wall: id, wall_colour: null })} />
      <div className="mt-2 flex items-center gap-2 text-sm">
        <label htmlFor="wall-colour">Custom colour</label>
        <input id="wall-colour" type="color" value={finish.wall_colour || wall?.colour || "#ffffff"} onChange={(e) => onChange({ wall_colour: e.target.value })} className="h-8 w-12 cursor-pointer rounded border border-stone-300" />
        {finish.wall_colour && (
          <button className="text-xs text-stone-500 underline" onClick={() => onChange({ wall_colour: null })}>
            Reset
          </button>
        )}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div>
          <label className="label" htmlFor="feature-side">
            Feature wall
          </label>
          <select
            id="feature-side"
            className="input"
            value={finish.feature_side ?? ""}
            onChange={(e) => {
              const side = (e.target.value || null) as Side | null;
              onChange({ feature_side: side, feature: side ? finish.feature || "exposed_brick" : null });
            }}
          >
            <option value="">None</option>
            <option value="front">Front wall</option>
            <option value="rear">Rear wall</option>
            <option value="left">Left wall</option>
            <option value="right">Right wall</option>
          </select>
        </div>
        {finish.feature_side && (
          <div>
            <label className="label" htmlFor="feature-finish">
              Feature finish
            </label>
            <select id="feature-finish" className="input" value={finish.feature ?? ""} onChange={(e) => onChange({ feature: e.target.value })}>
              {catalog.wall_finishes.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      <h3 className="mt-4 mb-2 font-medium">Floor</h3>
      <Swatches name="Floor finish" list={catalog.floor_finishes} value={finish.floor} onPick={(id) => onChange({ floor: id })} />
      {editable && (
        <button className="btn-secondary mt-3" onClick={onApplyAll}>
          Use these walls and floor in every dry room
        </button>
      )}
    </section>
  );
}

export { inr };
