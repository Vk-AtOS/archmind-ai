"use client";

import { useEffect, useState } from "react";

import { api, errorText } from "@/lib/api";
import { money } from "@/lib/types";

type Actual = { id: string; total: number; currency: string; estimate_total: number; error_pct: number; note: string; at: string };

export default function ActualCost({ optionId, currency }: { optionId: string; currency: string }) {
  const [rows, setRows] = useState<Actual[]>([]);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ data_use_opt_in: boolean }>("/org/settings").then((s) => setEnabled(s.data_use_opt_in), () => setEnabled(false));
    api<Actual[]>(`/options/${optionId}/actual-costs`).then(setRows, () => undefined);
  }, [optionId]);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setError("");
    try {
      const row = await api<Actual>(`/options/${optionId}/actual-costs`, {
        method: "POST",
        body: { total: Number(f.get("total")), currency, note: f.get("note") },
      });
      setRows((r) => [row, ...r]);
      form.reset();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <section className="card">
      <h2 className="mb-1 font-medium">Actual build cost</h2>
      {enabled === false && (
        <p className="text-sm text-stone-500">
          Recording actual costs is off for your organisation. An admin can turn it on in Settings.
        </p>
      )}
      {enabled && (
        <form onSubmit={save} className="flex flex-wrap items-end gap-2">
          <div>
            <label className="label" htmlFor="total">
              Actual total ({currency})
            </label>
            <input id="total" name="total" type="number" min={1} step={1} required className="input w-44" />
          </div>
          <div className="min-w-48 flex-1">
            <label className="label" htmlFor="note">
              Note
            </label>
            <input id="note" name="note" maxLength={1000} className="input" placeholder="Final contractor bill" />
          </div>
          <button className="btn">Record</button>
        </form>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {rows.length > 0 && (
        <table className="mt-3 w-full text-sm" data-testid="actual-costs">
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-stone-100">
                <td className="py-1">{new Date(r.at).toLocaleDateString()}</td>
                <td className="py-1 text-right">{money(r.total, r.currency)}</td>
                <td className="py-1 text-right text-stone-500">est. {money(r.estimate_total, r.currency)}</td>
                <td className={`py-1 text-right ${Math.abs(r.error_pct) > 10 ? "text-amber-700" : "text-green-700"}`}>
                  {r.error_pct > 0 ? "+" : ""}
                  {r.error_pct}%
                </td>
                <td className="py-1 pl-2 text-stone-500">{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
