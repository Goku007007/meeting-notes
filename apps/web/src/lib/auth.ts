const GUEST_TOKEN_KEY = "meeting-notes:guest-token";
const BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

let pendingTokenRequest: Promise<string> | null = null;

function getBaseUrl(): string {
  if (!BASE) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  return BASE;
}

export function getGuestToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(GUEST_TOKEN_KEY);
}

export function clearGuestToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(GUEST_TOKEN_KEY);
}

export async function ensureGuestToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const existing = getGuestToken();
  if (existing) return existing;

  if (!pendingTokenRequest) {
    pendingTokenRequest = fetch(`${getBaseUrl()}/sessions/guest`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Failed to create guest session (${res.status})`);
        }
        return (await res.json()) as { token: string };
      })
      .then((data) => {
        if (!data?.token) throw new Error("Guest session token missing");
        window.localStorage.setItem(GUEST_TOKEN_KEY, data.token);
        return data.token;
      })
      .finally(() => {
        pendingTokenRequest = null;
      });
  }

  return pendingTokenRequest;
}
