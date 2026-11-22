"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import Shell from "@/components/Shell";
import { api, errorText } from "@/lib/api";
import type { Project } from "@/lib/types";

export default function Projects() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState("");

  const load = () => api<Project[]>("/projects").then(setProjects, (e) => setError(errorText(e)));
  useEffect(() => {
    load();
  }, []);

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const form = new FormData(formEl);
    setError("");
    try {
      await api("/projects", { method: "POST", body: { name: form.get("name"), location: form.get("location") } });
      formEl.reset();
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Shell>
      <h1 className="mb-4 text-xl font-semibold">Projects</h1>
      <form onSubmit={create} className="card mb-6 flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <label className="label" htmlFor="name">
            Project name
          </label>
          <input id="name" name="name" required maxLength={200} className="input" placeholder="House for Mr. Rao" />
        </div>
        <div className="min-w-48 flex-1">
          <label className="label" htmlFor="location">
            Location
          </label>
          <input id="location" name="location" maxLength={300} className="input" placeholder="Plot 12, Sector 4" />
        </div>
        <button className="btn">New project</button>
      </form>
      {error && (
        <p role="alert" className="mb-4 text-sm text-red-700">
          {error}
        </p>
      )}
      {projects === null ? (
        <p className="text-sm text-stone-500">Loading…</p>
      ) : projects.length === 0 ? (
        <p className="text-sm text-stone-500">No projects yet. Create one above.</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <li key={p.id}>
              <Link href={`/projects/${p.id}`} className="card block hover:border-stone-400">
                <div className="font-medium">{p.name}</div>
                <div className="text-sm text-stone-500">{p.location || "No location"}</div>
                <div className="mt-2 text-xs text-stone-400">Rule pack: {p.rule_pack}</div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Shell>
  );
}
