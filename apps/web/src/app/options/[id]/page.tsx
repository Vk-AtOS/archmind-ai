"use client";

import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import ActualCost from "@/components/ActualCost";
import RateLayout from "@/components/RateLayout";
import Shell from "@/components/Shell";
import { api, errorText } from "@/lib/api";
import { money, type OptionDetail } from "@/lib/types";

const Model3D = dynamic(() => import("@/components/Model3D"), { ssr: false });

const RESULT_STYLE = { pass: "text-green-700", fail: "text-red-700 font-medium", unknown: "text-amber-700" };

export default function OptionPage() {
  const { id } = useParams<{ id: string }>();
  const [opt, setOpt] = useState<OptionDetail | null>(null);
  const [error, setError] = useState("");
  const [floor, setFloor] = useState(0);
  const [floor3d, setFloor3d] = useState<number | "all">(0);

  useEffect(() => {
    api<OptionDetail>(`/options/${id}`).then(setOpt, (e) => setError(errorText(e)));
  }, [id]);

  if (error)
    return (
      <Shell>
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      </Shell>
    );
  if (!opt)
    return (
      <Shell>
        <p className="text-sm text-stone-500">Loading…</p>
      </Shell>
    );

  const fails = opt.checks.filter((c) => c.result === "fail").length;
  const unknowns = opt.checks.filter((c) => c.result === "unknown").length;
  const est = opt.estimate;

  function downloadCsv() {
    const rows = [
      ["item", "description", "qty", "unit", "rate", "amount", "currency"],
      ...est.lines.map((l) => [l.item_id, l.description, l.qty, l.unit, l.rate, l.amount, est.currency]),
      ["total", "", "", "", "", est.total, est.currency],
      ["note", est.label, "", "", "", "", ""],
    ];
    const csv = rows.map((r) => r.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `archmind-${opt!.label}-estimate.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <Shell>
      <button onClick={() => history.back()} className="text-sm text-stone-500 hover:underline">
        ← Back
      </button>
      <div className="mt-1 mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{opt.label.replace("option-", "Option ")}</h1>
          <p className={`text-sm ${fails ? "text-red-700" : "text-green-700"}`} data-testid="check-summary">
            {fails ? `${fails} failed checks` : "All hard-rule checks pass"}
            {unknowns ? ` · ${unknowns} unknown` : ""} · rule pack {opt.layout.rule_pack} (provisional)
          </p>
        </div>
        <div className="flex gap-2">
          <a className="btn" href={`/api/v1/options/${opt.id}/model.ifc`} data-testid="download-ifc">
            Download IFC
          </a>
          <button className="btn-secondary" onClick={downloadCsv}>
            Estimate CSV
          </button>
          <a className="btn-secondary" href={`/options/${opt.id}/report`} data-testid="report-link">
            Report / PDF
          </a>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-medium">Plan</h2>
            {opt.layout.floors.length > 1 && (
              <div className="flex gap-1">
                {opt.layout.floors.map((f) => (
                  <button
                    key={f.level}
                    onClick={() => setFloor(f.level)}
                    className={floor === f.level ? "btn" : "btn-secondary"}
                  >
                    {f.level === 0 ? "Ground" : `Floor ${f.level}`}
                  </button>
                ))}
              </div>
            )}
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element -- server-rendered SVG behind auth */}
          <img src={`/api/v1/options/${opt.id}/plans/${floor}.svg`} alt={`Plan of floor ${floor}`} className="w-full" />
        </section>
        <section className="card">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-medium">3D view</h2>
            <div className="flex gap-1" data-testid="floor3d-toggle">
              {[...opt.layout.floors.map((f) => f.level as number | "all"), ...(opt.layout.floors.length > 1 ? ["all" as const] : [])].map(
                (lv) => (
                  <button key={String(lv)} onClick={() => setFloor3d(lv)} className={floor3d === lv ? "btn" : "btn-secondary"}>
                    {lv === "all" ? "Whole house" : lv === 0 ? "Ground" : `Floor ${lv}`}
                  </button>
                ),
              )}
            </div>
          </div>
          <Model3D layout={opt.layout} level={floor3d} />
        </section>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-1 font-medium">Estimate</h2>
          <p className="mb-3 text-xs text-amber-700">{est.label}. {est.warnings.join(" ")}</p>
          <table className="w-full text-sm">
            <tbody>
              {est.lines.map((l) => (
                <tr key={l.item_id} className="border-b border-stone-100">
                  <td className="py-1">{l.description}</td>
                  <td className="py-1 text-right text-stone-500">
                    {l.qty} {l.unit} × {l.rate}
                  </td>
                  <td className="py-1 text-right">{money(l.amount, est.currency)}</td>
                </tr>
              ))}
              <tr className="font-medium">
                <td className="pt-2">Total</td>
                <td />
                <td className="pt-2 text-right" data-testid="estimate-total">
                  {money(est.total, est.currency)}
                </td>
              </tr>
            </tbody>
          </table>
          <p className="mt-3 text-xs text-stone-500">Excludes: {est.exclusions.join(", ")}.</p>
        </section>

        <ActualCost optionId={opt.id} currency={est.currency} />

        <RateLayout optionId={opt.id} />

        <section className="card">
          <h2 className="mb-3 font-medium">Rooms</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-stone-500">
              <tr>
                <th>Floor</th>
                <th>Room</th>
                <th className="text-right">Size (m)</th>
                <th className="text-right">Area (m²)</th>
              </tr>
            </thead>
            <tbody>
              {opt.schedule.map((r) => (
                <tr key={`${r.floor}-${r.name}`} className="border-b border-stone-100">
                  <td className="py-1">{r.floor}</td>
                  <td className="py-1">{r.name}</td>
                  <td className="py-1 text-right">
                    {r.width_m.toFixed(2)} × {r.depth_m.toFixed(2)}
                  </td>
                  <td className="py-1 text-right">{r.area_m2.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="card">
          <h2 className="mb-3 font-medium">Quantities</h2>
          <table className="w-full text-sm">
            <tbody>
              {opt.quantities.lines.map((q) => (
                <tr key={q.item_id} className="border-b border-stone-100" title={q.method}>
                  <td className="py-1">{q.description}</td>
                  <td className="py-1 text-right">
                    {q.qty} {q.unit}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-stone-500">Hover a row for its calculation method.</p>
        </section>

        <section className="card">
          <h2 className="mb-3 font-medium">Checks</h2>
          <div className="max-h-80 overflow-auto">
            <table className="w-full text-sm">
              <tbody>
                {opt.checks.map((c, i) => (
                  <tr key={i} className="border-b border-stone-100">
                    <td className="py-1">{c.rule_id}</td>
                    <td className="py-1 text-stone-500">{c.subject}</td>
                    <td className="py-1 text-right text-stone-500">
                      {c.measured ?? ""}
                      {c.limit !== null ? ` / ${c.limit}` : ""} {c.unit}
                    </td>
                    <td className={`py-1 text-right ${RESULT_STYLE[c.result]}`}>{c.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Shell>
  );
}
