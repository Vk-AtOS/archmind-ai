"use client";

// Interior studio (ARCH-156): auto-furnish by theme, then swap, move, recolour, add decor and
// plants, and change wall and floor finishes room by room. Fit checks and cost update as you work.
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AddItems, Finishes, inr, SelectedItem } from "@/components/interior/Panels";
import RoomEditor from "@/components/interior/RoomEditor";
import Shell from "@/components/Shell";
import { api, errorText } from "@/lib/api";
import { box, type Catalog, type CatalogItem, type Interior, type InteriorOut, nextRot, type Placement, type RoomFinish, snapToWall } from "@/lib/interior";

const Room3D = dynamic(() => import("@/components/interior/Room3D"), { ssr: false });

let seq = 0;
const newUid = (room: string) => `${room}-u${Date.now().toString(36)}${(seq++).toString(36)}`;

export default function InteriorStudio() {
  const { id } = useParams<{ id: string }>();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [data, setData] = useState<InteriorOut | null>(null);
  const [interior, setInterior] = useState<Interior | null>(null);
  const [roomId, setRoomId] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [theme, setTheme] = useState("modern");

  useEffect(() => {
    api<Catalog>("/interiors/catalog").then(setCatalog, (e) => setError(errorText(e)));
    api<InteriorOut>(`/options/${id}/interior`).then(
      (d) => {
        setData(d);
        setInterior(d.interior);
        setTheme(d.interior.theme);
        setRoomId((d.rooms.find((r) => r.type === "living") ?? d.rooms[0]).id);
      },
      (e) => setError(errorText(e)),
    );
  }, [id]);

  // Re-run fit checks and cost on the server shortly after each edit.
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => {
    if (!interior || !dirty) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api<InteriorOut>(`/options/${id}/interior/check`, { method: "POST", body: { interior, base_revision: data?.revision ?? 0 } }).then(
        (d) => setData((old) => (old ? { ...old, issues: d.issues, cost: d.cost } : d)),
        (e) => setError(errorText(e)),
      );
    }, 350);
    return () => clearTimeout(timer.current);
  }, [interior, dirty, id, data?.revision]);

  const byId = useMemo(() => new Map((catalog?.items ?? []).map((i) => [i.id, i] as const)), [catalog]);
  const walls = useMemo(() => new Map((catalog?.wall_finishes ?? []).map((f) => [f.id, f] as const)), [catalog]);
  const floors = useMemo(() => new Map((catalog?.floor_finishes ?? []).map((f) => [f.id, f] as const)), [catalog]);

  const edit = useCallback((fn: (i: Interior) => Interior) => {
    setInterior((i) => (i ? fn(i) : i));
    setDirty(true);
    setNote("");
  }, []);
  const patchItem = useCallback(
    (uid: string, patch: Partial<Placement>) => edit((i) => ({ ...i, items: i.items.map((p) => (p.uid === uid ? { ...p, ...patch } : p)) })),
    [edit],
  );
  const removeItem = useCallback(
    (uid: string) => {
      edit((i) => ({ ...i, items: i.items.filter((p) => p.uid !== uid) }));
      setSelected(null);
    },
    [edit],
  );
  const rotateItem = useCallback(
    (uid: string) =>
      edit((i) => ({
        ...i,
        items: i.items.map((p) => {
          if (p.uid !== uid) return p;
          const it = byId.get(p.item_id);
          const room = data?.rooms.find((r) => r.id === p.room_id);
          if (it?.layer === "wall" && room) return { ...p, ...snapToWall(it, p.x, p.y, room) }; // wall items face the room
          return { ...p, rot: nextRot(p.rot) };
        }),
      })),
    [edit, byId, data?.rooms],
  );

  if (error && !data)
    return (
      <Shell>
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      </Shell>
    );
  if (!data || !interior || !catalog)
    return (
      <Shell>
        <p className="text-sm text-stone-500">Loading the interior studio…</p>
      </Shell>
    );

  const room = data.rooms.find((r) => r.id === roomId) ?? data.rooms[0];
  const finish = interior.rooms[room.id];
  const roomItems = interior.items.filter((p) => p.room_id === room.id);
  const roomIssues = data.issues.filter((i) => i.room_id === room.id);
  const sel = interior.items.find((p) => p.uid === selected && p.room_id === room.id) ?? null;
  const editable = data.can_edit;
  const floorsList = [...new Set(data.rooms.map((r) => r.floor))];
  const groupTotals = data.cost.lines.reduce<Record<string, number>>((acc, l) => ({ ...acc, [l.group]: (acc[l.group] ?? 0) + l.amount }), {});

  function add(it: CatalogItem) {
    const uid = newUid(room.id);
    let x = room.w / 2;
    let y = room.d / 2;
    let rot: Placement["rot"] = 0;
    if (it.layer === "wall") ({ x, y, rot } = snapToWall(it, room.w / 2, 0.1, room));
    if (it.layer === "top") {
      const host = roomItems.find((p) => byId.get(p.item_id)?.surface);
      if (host) ({ x, y } = host);
    }
    edit((i) => ({ ...i, items: [...i.items, { uid, item_id: it.id, room_id: room.id, x, y, rot }] }));
    setSelected(uid);
  }

  async function applyTheme() {
    if ((dirty || data!.saved) && !window.confirm("Replace the interior of every room with this theme? Unsaved edits are lost.")) return;
    setBusy("theme");
    setError("");
    try {
      const d = await api<InteriorOut>(`/options/${id}/interior/auto`, { method: "POST", body: { theme } });
      setData((old) => ({ ...d, revision: old?.revision ?? d.revision, saved: old?.saved ?? d.saved }));
      setInterior(d.interior);
      setSelected(null);
      setDirty(true);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy("");
    }
  }

  async function save() {
    setBusy("save");
    setError("");
    try {
      const d = await api<InteriorOut>(`/options/${id}/interior`, { method: "PUT", body: { interior, base_revision: data!.revision } });
      setData(d);
      setDirty(false);
      setNote(`Saved (revision ${d.revision})`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy("");
    }
  }

  function setFinish(patch: Partial<RoomFinish>) {
    edit((i) => ({ ...i, rooms: { ...i.rooms, [room.id]: { ...i.rooms[room.id], ...patch } } }));
  }
  function applyAll() {
    edit((i) => ({
      ...i,
      rooms: Object.fromEntries(
        Object.entries(i.rooms).map(([rid, rf]) => {
          const r = data!.rooms.find((x) => x.id === rid);
          const dry = r && r.type !== "bathroom" && r.type !== "kitchen";
          return [rid, dry ? { ...rf, wall: finish.wall, wall_colour: finish.wall_colour, floor: finish.floor } : rf];
        }),
      ),
    }));
  }

  return (
    <Shell>
      <Link href={`/options/${id}`} className="text-sm text-stone-500 hover:underline">
        ← Option
      </Link>
      <div className="mt-1 mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Interior studio</h1>
          <p className="text-sm text-stone-500">
            Furniture, decor, plants and finishes, room by room. Prices are samples ({catalog.source}).
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label className="label" htmlFor="theme">
              Design theme
            </label>
            <select id="theme" className="input" value={theme} onChange={(e) => setTheme(e.target.value)} disabled={!editable}>
              {catalog.themes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          {editable && (
            <>
              <button className="btn-secondary" onClick={applyTheme} disabled={!!busy}>
                {busy === "theme" ? "Furnishing…" : "Furnish whole house"}
              </button>
              <button className="btn" onClick={save} disabled={!!busy || !dirty} data-testid="save-interior">
                {busy === "save" ? "Saving…" : dirty ? "Save interior" : "Saved"}
              </button>
            </>
          )}
        </div>
      </div>
      {!editable && <p className="mb-3 text-sm text-stone-500">View only: your role cannot edit interiors.</p>}
      {!data.saved && !dirty && <p className="mb-3 text-sm text-amber-700">Suggested interior in the {interior.theme} theme. Edit anything, then save it.</p>}
      {error && (
        <p role="alert" className="mb-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {note && <p className="mb-3 text-sm text-green-700">{note}</p>}

      <div className="mb-4 flex flex-wrap gap-4" data-testid="room-picker">
        {floorsList.map((f) => (
          <div key={f} className="flex flex-wrap items-center gap-1">
            <span className="mr-1 text-xs text-stone-500">{f === 0 ? "Ground" : `Floor ${f}`}</span>
            {data.rooms
              .filter((r) => r.floor === f)
              .map((r) => {
                const n = data.issues.filter((i) => i.room_id === r.id && i.result === "fail").length;
                return (
                  <button key={r.id} className={r.id === room.id ? "btn" : "btn-secondary"} onClick={() => (setRoomId(r.id), setSelected(null))}>
                    {r.name}
                    {n > 0 && <span className="ml-1 text-red-600">●</span>}
                  </button>
                );
              })}
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-2 font-medium">
            {room.name} plan <span className="text-xs font-normal text-stone-500">· drag to move · R rotate · Delete remove · arrows nudge</span>
          </h2>
          <RoomEditor
            room={room}
            items={roomItems}
            byId={byId}
            issues={roomIssues}
            selected={selected}
            editable={editable}
            onSelect={setSelected}
            onMove={patchItem}
            onRotate={rotateItem}
            onDelete={removeItem}
          />
        </section>
        <section className="card">
          <h2 className="mb-2 font-medium">{room.name} in 3D</h2>
          <Room3D room={room} finish={finish} items={roomItems} byId={byId} walls={walls} floors={floors} selected={selected} onSelect={setSelected} />
        </section>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6">
          {sel ? (
            <SelectedItem
              p={sel}
              catalog={catalog}
              room={room}
              editable={editable}
              onSwap={(itemId) => {
                const it = byId.get(itemId)!;
                patchItem(sel.uid, it.layer === "wall" ? { item_id: itemId, ...snapToWall(it, sel.x, sel.y, room) } : { item_id: itemId });
              }}
              onColour={(c) => patchItem(sel.uid, { colour: c })}
              onRotate={() => rotateItem(sel.uid)}
              onDuplicate={() => {
                const uid = newUid(room.id);
                const it = byId.get(sel.item_id)!;
                const [x0, , x1] = box(it, sel);
                edit((i) => ({ ...i, items: [...i.items, { ...sel, uid, x: +(sel.x + (x1 - x0) + 0.1).toFixed(3) }] }));
                setSelected(uid);
              }}
              onDelete={() => removeItem(sel.uid)}
            />
          ) : (
            <section className="card text-sm text-stone-500">Select an item in the plan or the 3D view to swap, recolour, rotate or remove it.</section>
          )}
          {editable && <AddItems catalog={catalog} room={room} onAdd={add} />}
        </div>
        <Finishes catalog={catalog} room={room} finish={finish} editable={editable} onChange={setFinish} onApplyAll={applyAll} />
        <div className="space-y-6">
          <section className="card">
            <h3 className="mb-2 font-medium">Fit checks · {room.name}</h3>
            {roomIssues.length === 0 ? (
              <p className="text-sm text-green-700" data-testid="fit-ok">
                Everything fits: inside the room, no overlaps, doors and clearances free.
              </p>
            ) : (
              <ul className="space-y-1 text-sm" data-testid="fit-issues">
                {roomIssues.map((i, k) => (
                  <li key={k}>
                    <button className={`text-left hover:underline ${i.result === "fail" ? "text-red-700" : "text-amber-700"}`} onClick={() => setSelected(i.uid)}>
                      {i.result === "fail" ? "✕" : "!"} {i.message}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="card">
            <h3 className="mb-1 font-medium">Interiors cost (whole house)</h3>
            <p className="mb-2 text-xs text-amber-700">{data.cost.label}</p>
            <table className="w-full text-sm">
              <tbody>
                {Object.entries(groupTotals).map(([g, v]) => (
                  <tr key={g} className="border-b border-stone-100">
                    <td className="py-1">{g}</td>
                    <td className="py-1 text-right">{inr(v)}</td>
                  </tr>
                ))}
                <tr className="font-medium">
                  <td className="pt-2">Total</td>
                  <td className="pt-2 text-right" data-testid="interior-total">
                    {inr(data.cost.total)}
                  </td>
                </tr>
              </tbody>
            </table>
            <details className="mt-2 text-xs text-stone-500">
              <summary className="cursor-pointer">Line items</summary>
              <ul className="mt-1 space-y-0.5">
                {data.cost.lines.map((l, k) => (
                  <li key={k}>
                    {l.description}: {l.qty} {l.unit === "m2" ? "m²" : l.unit} × {inr(l.rate)} = {inr(l.amount)}
                  </li>
                ))}
              </ul>
              <p className="mt-1">{data.cost.warnings.join(" ")}</p>
            </details>
          </section>
        </div>
      </div>
    </Shell>
  );
}
