const BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

export type ApiError = {
  message: string;
  status: number;
};

function getBaseUrl(): string {
  if (!BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  return BASE;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${getBaseUrl()}${path}`, { cache: "no-store" });
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${getBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

async function toApiError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status})`;

  try {
    const data = (await res.json()) as { detail?: string; message?: string };
    message = data?.detail ?? data?.message ?? message;
  } catch {
    // Ignore JSON parse failures and keep fallback message.
  }

  return { message, status: res.status };
}

