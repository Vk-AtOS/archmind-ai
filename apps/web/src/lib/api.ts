// Thin fetch wrapper. Same-origin /api/* calls carry the session cookie; mutations send JSON,
// which the API requires (CSRF defence).

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
  }
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const r = await fetch(`/api/v1${path}`, {
    method: init.method ?? "GET",
    headers: init.body === undefined && init.method !== "POST" ? undefined : { "content-type": "application/json" },
    body: init.body === undefined ? (init.method === "POST" ? "{}" : undefined) : JSON.stringify(init.body),
    credentials: "same-origin",
  });
  if (r.status === 401 && !path.startsWith("/auth/login")) {
    window.location.href = "/login";
    throw new ApiError(401, "Signed out");
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new ApiError(r.status, body.detail ?? `Request failed (${r.status})`);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}

/** Human-readable message from an API error, including FastAPI field errors. */
export function errorText(e: unknown): string {
  if (e instanceof ApiError && Array.isArray(e.detail)) {
    return e.detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = (d.loc ?? []).filter((x) => x !== "body").join(".");
        const msg = (d.msg ?? "").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("; ");
  }
  return e instanceof Error ? e.message : String(e);
}
