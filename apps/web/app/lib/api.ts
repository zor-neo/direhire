const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const syntheticLocalUser = process.env.NEXT_PUBLIC_DEV_USER_ID;

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

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  if (syntheticLocalUser) headers.set("X-DireHire-User-ID", syntheticLocalUser);
  const csrfToken = cookieValue("direhire_csrf");
  if (csrfToken && init?.method && !["GET", "HEAD"].includes(init.method)) {
    headers.set("X-CSRF-Token", csrfToken);
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
