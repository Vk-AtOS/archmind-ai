"use client";

import { useEffect, useState } from "react";

import Shell from "@/components/Shell";
import { api, errorText } from "@/lib/api";

export default function Settings() {
  const [optIn, setOptIn] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ data_use_opt_in: boolean }>("/org/settings").then((s) => setOptIn(s.data_use_opt_in), (e) => setError(errorText(e)));
  }, []);

  async function toggle(value: boolean) {
    setError("");
    setOptIn(value); // show the change immediately; revert if the server refuses
    try {
      const s = await api<{ data_use_opt_in: boolean }>("/org/settings", { method: "PUT", body: { data_use_opt_in: value } });
      setOptIn(s.data_use_opt_in);
    } catch (e) {
      setOptIn(!value);
      setError(errorText(e));
    }
  }

  return (
    <Shell>
      <h1 className="mb-4 text-xl font-semibold">Organisation settings</h1>
      <section className="card max-w-2xl">
        <h2 className="font-medium">Actual build costs</h2>
        <p className="mt-1 text-sm text-stone-600">
          When on, your team can record the real cost of a built option next to its estimate. ArchMind uses these
          figures to measure and improve estimate accuracy for your organisation. Off by default; only admins can change
          it. Data-use terms: ARCH-145.
        </p>
        {optIn !== null && (
          <label className="mt-4 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={optIn} onChange={(e) => toggle(e.target.checked)} data-testid="opt-in" />
            Allow recording actual costs
          </label>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {error}
          </p>
        )}
      </section>
    </Shell>
  );
}
