"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Me } from "@/lib/types";

export default function Shell({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api<Me>("/me").then(setMe, () => undefined); // 401 redirects to /login inside api()
  }, []);

  async function signOut() {
    await api("/auth/logout", { method: "POST" });
    window.location.href = "/login";
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link href="/projects" className="font-semibold">
            ArchMind
          </Link>
          {me && (
            <div className="flex items-center gap-3 text-sm text-stone-600">
              {me.role === "admin" && (
                <Link href="/settings" className="hover:underline">
                  Settings
                </Link>
              )}
              <span data-testid="whoami">
                {me.name} · {me.role.replace("_", " ")}
              </span>
              <button className="btn-secondary" onClick={signOut}>
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{me ? children : <p className="text-sm text-stone-500">Loading…</p>}</main>
    </div>
  );
}
