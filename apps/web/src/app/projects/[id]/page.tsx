"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import Shell from "@/components/Shell";
import { api, errorText } from "@/lib/api";
import { type BriefOut, money, type Project } from "@/lib/types";
import { areaU, fromUnit, lenU, toUnit, useUnit } from "@/lib/units";

const num = (f: FormData, k: string) => Number(f.get(k));

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [briefs, setBriefs] = useState<BriefOut[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const unit = useUnit();
  const metres = (f: FormData, k: string) => Math.round(fromUnit(num(f, k), unit) * 1000) / 1000;

  useEffect(() => {
    api<Project>(`/projects/${id}`).then(setProject, (e) => setError(errorText(e)));
    api<BriefOut[]>(`/projects/${id}/briefs`).then(setBriefs, (e) => setError(errorText(e)));
  }, [id]);

  async function generate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const rooms = [
      { type: "living" },
      { type: "kitchen" },
      { type: "bedroom", count: num(f, "bedrooms") },
      { type: "bathroom", count: num(f, "bathrooms") },
      ...(f.get("dining") ? [{ type: "dining" }] : []),
    ];
    const brief = {
      plot_width_m: metres(f, "plot_width_m"),
      plot_depth_m: metres(f, "plot_depth_m"),
      setbacks: { front: metres(f, "front"), rear: metres(f, "rear"), left: metres(f, "left"), right: metres(f, "right") },
      floors: num(f, "floors"),
      rooms,
    };
    setBusy(true);
    setError("");
    try {
      const created = await api<BriefOut>(`/projects/${id}/briefs`, { method: "POST", body: brief });
      setBriefs((b) => [created, ...(b ?? [])]);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  // Lengths are typed in the chosen unit and sent to the API in metres. Defaults round UP so that
  // 3 m shows as 9.85 ft (3.0023 m), not 9.84 ft (2.9992 m), which would fail a 3 m minimum setback.
  const lengthField = (name: string, label: string, metresValue: number) =>
    field(name, `${label} (${unit})`, Math.ceil(toUnit(metresValue, unit) * 100 - 1e-9) / 100, unit === "cm" || unit === "mm" ? 1 : 0.01);
  const field = (name: string, label: string, value: number, step = 0.1, min = 0) => (
    <div>
      <label className="label" htmlFor={name}>
        {label}
      </label>
      <input key={`${name}-${unit}`} id={name} name={name} type="number" step={step} min={min} defaultValue={value} required className="input" />
    </div>
  );

  return (
    <Shell>
      <Link href="/projects" className="text-sm text-stone-500 hover:underline">
        ← Projects
      </Link>
      <h1 className="mt-1 text-xl font-semibold">{project?.name ?? "…"}</h1>
      <p className="mb-6 text-sm text-stone-500">
        {project?.location || "No location"} · rule pack {project?.rule_pack} (provisional placeholder values)
      </p>

      <form onSubmit={generate} className="card mb-8">
        <h2 className="mb-3 font-medium">New brief</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {lengthField("plot_width_m", "Plot width", 12)}
          {lengthField("plot_depth_m", "Plot depth", 15)}
          <div>
            <label className="label" htmlFor="floors">
              Floors
            </label>
            <select id="floors" name="floors" defaultValue="2" className="input">
              <option value="1">Ground only</option>
              <option value="2">Ground + first</option>
            </select>
          </div>
          <div />
          {lengthField("front", "Front setback", 3)}
          {lengthField("rear", "Rear setback", 1.5)}
          {lengthField("left", "Left setback", 1)}
          {lengthField("right", "Right setback", 1)}
          {field("bedrooms", "Bedrooms", 3, 1, 1)}
          {field("bathrooms", "Bathrooms", 2, 1, 1)}
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input type="checkbox" name="dining" defaultChecked /> Separate dining room
          </label>
        </div>
        <p className="mt-3 text-xs text-stone-500">Living room and kitchen are always included.</p>
        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {error}
          </p>
        )}
        <button className="btn mt-4" disabled={busy}>
          {busy ? "Generating…" : "Generate options"}
        </button>
      </form>

      <h2 className="mb-3 font-medium">Briefs and options</h2>
      {briefs === null ? (
        <p className="text-sm text-stone-500">Loading…</p>
      ) : briefs.length === 0 ? (
        <p className="text-sm text-stone-500">No briefs yet. Fill in the form above to generate design options.</p>
      ) : (
        briefs.map((b) => (
          <section key={b.id} className="mb-6">
            <p className="mb-2 text-xs text-stone-500">
              Brief {new Date(b.created_at).toLocaleString()} · plot {lenU(Number(b.data.plot_width_m), unit)} × {lenU(Number(b.data.plot_depth_m), unit)}
            </p>
            <ul className="grid gap-3 sm:grid-cols-3">
              {b.options.map((o) => (
                <li key={o.id}>
                  <Link href={`/options/${o.id}`} className="card block hover:border-stone-400" data-testid="option-card">
                    <div className="font-medium">{o.label.replace("option-", "Option ")}</div>
                    <div className="mt-1 text-sm">
                      Score {o.score.toFixed(2)} · {areaU(o.built_up_m2, unit)} built-up
                    </div>
                    <div className="text-sm">{money(o.estimate_total, o.currency)} indicative</div>
                    <div className={`mt-2 text-xs ${o.failed_checks ? "text-red-700" : "text-green-700"}`}>
                      {o.failed_checks ? `${o.failed_checks} failed checks` : "All checks pass"}
                      {o.unknown_checks ? ` · ${o.unknown_checks} unknown` : ""}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </Shell>
  );
}
