import type { ApiErrorBody } from "@/types/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

/** Called when a request returns 401 so the shell can drop a stale session. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler) {
  onUnauthorized = handler;
}

export function loadFailureMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 401) {
    return "Your session expired. Sign in again.";
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

async function parseError(res: Response): Promise<ApiError> {
  const text = await res.text();
  try {
    const body = JSON.parse(text) as ApiErrorBody;
    return new ApiError(res.status, body.code ?? "ERROR", body.message ?? text, body.detail);
  } catch {
    return new ApiError(res.status, "ERROR", text || res.statusText);
  }
}

export async function api<T>(
  path: string,
  opts: RequestInit & { json?: unknown; skipAuthRedirect?: boolean } = {},
): Promise<T> {
  const { json, headers: initHeaders, skipAuthRedirect, ...rest } = opts;
  const headers = new Headers(initHeaders);

  let body: BodyInit | undefined = rest.body ?? undefined;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  const res = await fetch(path, {
    ...rest,
    credentials: "include",
    headers,
    body,
  });

  if (!res.ok) {
    const error = await parseError(res);
    if (error.status === 401 && !skipAuthRedirect && !path.startsWith("/v1/auth/login")) {
      onUnauthorized?.();
    }
    throw error;
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export function apiForm<T>(path: string, form: FormData, method = "POST"): Promise<T> {
  return api<T>(path, { method, body: form });
}
