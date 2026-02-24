import { clearGuestToken, ensureGuestToken } from "@/lib/auth";

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

async function authorizedFetch(input: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers ?? {});
  const token = await ensureGuestToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response = await fetch(input, {
    ...init,
    headers,
    credentials: "include",
  });

  // Recover from stale/expired guest tokens by creating a fresh session once.
  if (response.status === 401 && typeof window !== "undefined") {
    clearGuestToken();
    const nextToken = await ensureGuestToken();
    if (nextToken) {
      headers.set("Authorization", `Bearer ${nextToken}`);
      response = await fetch(input, {
        ...init,
        headers,
        credentials: "include",
      });
    }
  }

  return response;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await authorizedFetch(`${getBaseUrl()}${path}`, { cache: "no-store" });
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await authorizedFetch(`${getBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await authorizedFetch(`${getBaseUrl()}${path}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

async function toApiError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status})`;

  try {
    const data = (await res.json()) as {
      detail?: string | { message?: string; code?: string; retry_after_seconds?: number };
      message?: string;
    };
    if (typeof data?.detail === "string") {
      message = data.detail;
    } else if (data?.detail && typeof data.detail === "object" && typeof data.detail.message === "string") {
      const retryHint =
        typeof data.detail.retry_after_seconds === "number"
          ? ` Retry after ${data.detail.retry_after_seconds}s.`
          : "";
      message = `${data.detail.message}${retryHint}`;
    } else {
      message = data?.message ?? message;
    }
  } catch {
    // Ignore JSON parse failures and keep fallback message.
  }

  return { message, status: res.status };
}
