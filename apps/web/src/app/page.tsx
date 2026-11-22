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
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">ArchMind</h1>
      <p className="mt-2 text-gray-600">Plot and brief to a checked house design with a build cost.</p>
      <p className="mt-6 text-sm" data-testid="api-status">{status}</p>
    </main>
  );
}
