import Link from "next/link";

export const dynamic = "force-dynamic";

async function apiStatus(): Promise<string> {
  const base = process.env.API_URL ?? "http://localhost:8000";
  try {
    const r = await fetch(`${base}/api/v1/health`, { cache: "no-store" });
    if (!r.ok) return `API error ${r.status}`;
    const body: { status: string; version: string } = await r.json();
    return `API ${body.status} (v${body.version})`;
  } catch {
    return "API unreachable";
  }
}

export default async function Home() {
  const status = await apiStatus();
  return (
    <main className="mx-auto mt-24 max-w-xl px-4">
      <h1 className="text-3xl font-semibold">ArchMind</h1>
      <p className="mt-2 text-stone-600">
        Plot and brief to a rule-compliant house design with a build cost, checked and traceable.
      </p>
      <Link href="/login" className="btn mt-6">
        Sign in
      </Link>
      <p className="mt-10 text-xs text-stone-400" data-testid="api-status">
        {status}
      </p>
    </main>
  );
}
