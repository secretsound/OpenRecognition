import { api, ApiError } from "@/api/client";
import type { JobOut, RecognizeResponse } from "@/types/api";

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

export function createVideoJob(
  file: File,
  params: Record<string, string | number | boolean | undefined>,
): Promise<JobOut> {
  return recognizeFile<JobOut>("/v1/jobs", file, params);
}

export function getJob(id: string): Promise<JobOut> {
  return api<JobOut>(`/v1/jobs/${id}`);
}

export async function pollJob(
  id: string,
  { intervalMs = 750, timeoutMs = 120_000 } = {},
): Promise<RecognizeResponse> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const job = await getJob(id);
    if (job.status === "completed" && job.result) return job.result;
    if (job.status === "failed") {
      throw new ApiError(500, "JOB_FAILED", job.error || "Video job failed");
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new ApiError(408, "JOB_TIMEOUT", "Video is taking too long. Try a shorter clip.");
}
