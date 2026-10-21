export function buildRecognizeUrl(
  path: string,
  params: Record<string, string | number | boolean | undefined>,
): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      qs.set(key, String(value));
    }
  }
  const query = qs.toString();
  return query ? `${path}?${query}` : path;
}

import { ApiError } from "@/api/client";

export async function recognizeFile<T>(
  path: string,
  file: File,
  params: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const url = buildRecognizeUrl(path, params);
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    try {
      const body = JSON.parse(text) as { code: string; message: string };
      throw new ApiError(res.status, body.code ?? "ERROR", body.message ?? text);
    } catch (e) {
      if (e instanceof ApiError) throw e;
      throw new ApiError(res.status, "ERROR", text || res.statusText);
    }
  }
  return res.json() as Promise<T>;
}
