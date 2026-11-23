"use client";

// Printable option report (ARCH-87). "Save as PDF" from the browser print dialog gives the PDF:
// no server-side PDF library needed. Every figure states its source and limits.
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { api, errorText } from "@/lib/api";
import UnitPicker from "@/components/UnitPicker";
import { money, type OptionDetail } from "@/lib/types";
import { area, areaLabel, checkText, len, qtyText, rateText, useUnit } from "@/lib/units";

export default function Report() {
  const { id } = useParams<{ id: string }>();
  const [opt, setOpt] = useState<OptionDetail | null>(null);
  const [error, setError] = useState("");
  const unit = useUnit();

  useEffect(() => {
    api<OptionDetail>(`/options/${id}`).then(setOpt, (e) => setError(errorText(e)));
  }, [id]);

  if (error) return <p role="alert" className="p-8 text-sm text-red-700">{error}</p>;
  if (!opt) return <p className="p-8 text-sm text-stone-500">Loading…</p>;

  const est = opt.estimate;
  const fails = opt.checks.filter((c) => c.result === "fail").length;
  const unknowns = opt.checks.filter((c) => c.result === "unknown").length;
  const title = opt.label.replace("option-", "Option ");

  return (
    <main className="mx-auto max-w-4xl bg-white p-8 text-sm print:p-0">
      <div className="mb-6 flex items-start justify-between print:hidden">
        <button onClick={() => history.back()} className="btn-secondary">
          ← Back
        </button>
        <UnitPicker />
        <button onClick={() => window.print()} className="btn" data-testid="print">
          Print / Save as PDF
        </button>
      </div>

      <header className="mb-6 border-b border-stone-300 pb-3">
        <h1 className="text-2xl font-semibold">ArchMind design report · {title}</h1>
        <p className="text-stone-600">
          Generated {new Date().toLocaleString()} · rule pack {opt.layout.rule_pack} (provisional) · generator{" "}
          {opt.layout.generator_version} · rates {est.rate_table} · quantities v{opt.quantities.version}
        </p>
        <p className="mt-1 font-medium text-red-700">
          Concept design, not for construction. Structural, services and code approval require qualified professionals.
        </p>
      </header>

      <section className="mb-6">
        <h2 className="mb-1 text-lg font-medium">Summary</h2>
        <p>
          {fails ? `${fails} failed checks` : "All hard-rule checks pass"}
          {unknowns ? `, ${unknowns} unknown` : ""}. Indicative cost {money(est.total, est.currency)} ({est.label}).
        </p>
      </section>

      {opt.layout.floors.map((f) => (
        <section key={f.level} className="mb-6 break-inside-avoid">
          <h2 className="mb-2 text-lg font-medium">{f.level === 0 ? "Ground floor plan" : `Floor ${f.level} plan`}</h2>
          {/* eslint-disable-next-line @next/next/no-img-element -- server-rendered SVG behind auth */}
          <img src={`/api/v1/options/${opt.id}/plans/${f.level}.svg?units=${unit}`} alt={`Plan of floor ${f.level}`} className="mx-auto w-full print:max-h-[190mm] print:w-auto" />
        </section>
      ))}

      <section className="mb-6 break-inside-avoid">
        <h2 className="mb-2 text-lg font-medium">Room schedule</h2>
        <table className="w-full">
          <thead className="text-left text-xs text-stone-500">
            <tr>
              <th>Floor</th>
              <th>Room</th>
              <th className="text-right">Size ({unit})</th>
              <th className="text-right">Area ({areaLabel(unit)})</th>
            </tr>
          </thead>
          <tbody>
            {opt.schedule.map((r) => (
              <tr key={`${r.floor}-${r.name}`} className="border-b border-stone-200">
                <td>{r.floor}</td>
                <td>{r.name}</td>
                <td className="text-right">
                  {len(r.width_m, unit)} × {len(r.depth_m, unit)}
                </td>
                <td className="text-right">{area(r.area_m2, unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mb-6 break-inside-avoid">
        <h2 className="mb-2 text-lg font-medium">Indicative estimate</h2>
        <p className="mb-2 text-xs text-amber-700">{est.warnings.join(" ")}</p>
        <table className="w-full">
          <tbody>
            {est.lines.map((l) => (
              <tr key={l.item_id} className="border-b border-stone-200">
                <td>{l.description}</td>
                <td className="text-right text-stone-500">
                  {qtyText(l.qty, l.unit, unit)} × {rateText(l.rate, l.unit, unit)}
                </td>
                <td className="text-right">{money(l.amount, est.currency)}</td>
              </tr>
            ))}
            <tr className="font-medium">
              <td>Total</td>
              <td />
              <td className="text-right" data-testid="report-total">
                {money(est.total, est.currency)}
              </td>
            </tr>
          </tbody>
        </table>
        <p className="mt-2 text-xs text-stone-500">Excludes: {est.exclusions.join(", ")}.</p>
      </section>

      <section className="mb-6 break-inside-avoid">
        <h2 className="mb-2 text-lg font-medium">Quantities and methods</h2>
        <table className="w-full">
          <tbody>
            {opt.quantities.lines.map((q) => (
              <tr key={q.item_id} className="border-b border-stone-200">
                <td>{q.description}</td>
                <td className="text-right">
                  {qtyText(q.qty, q.unit, unit)}
                </td>
                <td className="pl-3 text-xs text-stone-500">{q.method}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="break-inside-avoid">
        <h2 className="mb-2 text-lg font-medium">Rule checks</h2>
        <table className="w-full">
          <tbody>
            {opt.checks.map((c, i) => (
              <tr key={i} className="border-b border-stone-200">
                <td>{c.rule_id}</td>
                <td className="text-stone-500">{c.subject}</td>
                <td className="text-right text-stone-500">{checkText(c, unit)}</td>
                <td className="text-right">{c.result}</td>
                <td className="pl-2 text-xs text-stone-500">{c.rule_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
