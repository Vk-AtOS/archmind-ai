"use client";

import { useEffect, useState } from "react";

import { api, errorText } from "@/lib/api";
import type { Me } from "@/lib/types";

const CRITERIA = [
  ["usability", "Usability"],
  ["circulation", "Circulation"],
  ["daylight", "Daylight and ventilation"],
  ["buildability", "Buildability"],
  ["client_ready", "Would show to a client"],
] as const;
type Key = (typeof CRITERIA)[number][0];
type Rating = Record<Key, number> & { comment: string; rater_id: string };
const RATERS = ["admin", "project_manager", "reviewer"];

export default function RateLayout({ optionId }: { optionId: string }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ratings, setRatings] = useState<Rating[]>([]);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Me>("/me").then(setMe, () => undefined);
    api<Rating[]>(`/options/${optionId}/ratings`).then(setRatings, () => undefined);
  }, [optionId]);

  const mine = ratings.find((r) => r.rater_id === me?.id);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = Object.fromEntries(CRITERIA.map(([k]) => [k, Number(f.get(k))]));
    setError("");
    setSaved("");
    try {
      const r = await api<Rating>(`/options/${optionId}/rating`, { method: "PUT", body: { ...body, comment: f.get("comment") } });
      setRatings((rs) => [r, ...rs.filter((x) => x.rater_id !== r.rater_id)]);
      setSaved("Rating saved");
    } catch (err) {
      setError(errorText(err));
    }
  }

  const avg = (k: Key) => (ratings.length ? ratings.reduce((s, r) => s + r[k], 0) / ratings.length : 0);

  return (
    <section className="card">
      <h2 className="mb-1 font-medium">Layout rating</h2>
      <p className="mb-3 text-xs text-stone-500">
        Architect and reviewer ratings (1 = poor, 5 = excellent) drive generator improvements.
        {ratings.length > 0 && ` ${ratings.length} rating${ratings.length > 1 ? "s" : ""} so far.`}
      </p>
      {ratings.length > 0 && (
        <ul className="mb-3 grid grid-cols-2 gap-x-4 text-sm" data-testid="rating-averages">
          {CRITERIA.map(([k, label]) => (
            <li key={k} className="flex justify-between border-b border-stone-100 py-1">
              <span>{label}</span>
              <span>{avg(k).toFixed(1)}</span>
            </li>
          ))}
        </ul>
      )}
      {me && RATERS.includes(me.role) ? (
        <form onSubmit={save} key={mine ? "has" : "none"}>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {CRITERIA.map(([k, label]) => (
              <div key={k}>
                <label className="label" htmlFor={`rate-${k}`}>
                  {label}
                </label>
                <select id={`rate-${k}`} name={k} defaultValue={mine?.[k] ?? 3} className="input">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          <label className="label mt-2" htmlFor="rate-comment">
            Comment
          </label>
          <textarea id="rate-comment" name="comment" maxLength={2000} defaultValue={mine?.comment ?? ""} className="input" rows={2} />
          <button className="btn mt-2">{mine ? "Update rating" : "Save rating"}</button>
          {saved && <span className="ml-3 text-sm text-green-700">{saved}</span>}
          {error && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {error}
            </p>
          )}
        </form>
      ) : (
        <p className="text-sm text-stone-500">Only admins, project managers and reviewers can rate layouts.</p>
      )}
    </section>
  );
}
