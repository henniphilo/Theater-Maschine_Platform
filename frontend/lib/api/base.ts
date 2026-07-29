/** API base URL — prefer same-origin proxy (/api/v1) to avoid CORS in Docker dev. */
export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window !== "undefined") return "/api/v1";
  return "http://127.0.0.1:8000/api/v1";
}

function isNetworkFetchError(err: unknown): boolean {
  return err instanceof TypeError && /fetch/i.test(err.message);
}

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const url = input.startsWith("http") ? input : `${apiBaseUrl()}${input.startsWith("/") ? input : `/${input}`}`;
  try {
    return await fetch(url, init);
  } catch (err) {
    if (isNetworkFetchError(err)) {
      throw new Error(
        "Backend nicht erreichbar. Bitte «make run» starten und http://localhost:3004/inszenierung nutzen."
      );
    }
    throw err;
  }
}

export async function apiFetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(input, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Anfrage fehlgeschlagen" }));
    const detail = (err as { detail?: string }).detail;
    throw new Error(typeof detail === "string" ? detail : "Anfrage fehlgeschlagen");
  }
  return res.json() as Promise<T>;
}
