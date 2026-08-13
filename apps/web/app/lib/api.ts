const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const syntheticLocalUser = process.env.NEXT_PUBLIC_DEV_USER_ID;
let remoteCsrfToken: string | undefined;

function cookieValue(name: string): string | undefined {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie
    .split("; ")
    .find((value) => value.startsWith(prefix))
    ?.slice(prefix.length);
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code = "REQUEST_FAILED",
    public readonly correlationId?: string,
  ) {
    super(message);
  }
}

async function loadCsrfToken(): Promise<string> {
  const localToken = cookieValue("direhire_csrf");
  if (localToken) return localToken;
  if (remoteCsrfToken) return remoteCsrfToken;

  // Dev mode: backend skips CSRF for synthetic dev users, so a placeholder suffices.
  if (syntheticLocalUser) {
    remoteCsrfToken = "dev-csrf-placeholder";
    return remoteCsrfToken;
  }

  const response = await fetch(`${apiBase}/auth/csrf-token`, {
    credentials: "include",
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      body?.error?.message ?? "The security token could not be loaded.",
      body?.error?.code,
      body?.error?.correlation_id,
    );
  }
  remoteCsrfToken = body.csrf_token;
  return remoteCsrfToken as string;
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  if (syntheticLocalUser) headers.set("X-DireHire-User-ID", syntheticLocalUser);
  const method = (init?.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRF-Token", await loadCsrfToken());
  }
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      body?.error?.message ?? "The request could not be completed.",
      body?.error?.code,
      body?.error?.correlation_id,
    );
  }
  return body as T;
}

export function apiLoginUrl(): string {
  return `${apiBase}/auth/login`;
}

export function apiSignupUrl(): string {
  return `${apiBase}/auth/signup`;
}

export function commaList(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function displayError(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  return error.correlationId
    ? `${error.message} Reference: ${error.correlationId.slice(0, 8)}`
    : error.message;
}
