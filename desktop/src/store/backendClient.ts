export type JobKind = "pipeline" | "demo";

export type JobEvent = {
  job_id: string;
  ts: string;
  type: "started" | "step" | "progress" | "completed" | "cancelled" | "error";
  step?: string;
  message?: string;
  pct?: number;
  status?: string;
};

export type JobRequest = {
  kind: JobKind;
  input_path?: string;
  output_dir?: string;
  options?: Record<string, unknown>;
};

type FilePathRequest = {
  path: string;
};

const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const BACKEND_HEALTH_URL = "http://127.0.0.1:8765/health";
const JOBS_URL = `${BACKEND_BASE_URL}/jobs`;
const BACKEND_TIMEOUT_MS = 1500;
const FS_EXISTS_URL = `${BACKEND_BASE_URL}/fs/exists`;
const FS_READ_TEXT_URL = `${BACKEND_BASE_URL}/fs/read_text`;

export const checkBackendHealth = async () => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const response = await fetch(BACKEND_HEALTH_URL, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`Backend health check failed: ${response.status}`);
    }
    const payload = (await response.json()) as { version?: string };
    return {
      ok: true,
      version: typeof payload.version === "string" ? payload.version : null
    };
  } finally {
    window.clearTimeout(timeoutId);
  }
};

export const startJob = async (requestBody: JobRequest) => {
  const response = await fetch(JOBS_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody)
  });
  if (!response.ok) {
    throw new Error(`Failed to start job: ${response.status}`);
  }
  const payload = (await response.json()) as { job_id?: string; events_url?: string };
  if (!payload.job_id) {
    throw new Error("Job response missing job_id");
  }
  const eventsUrl = payload.events_url ?? `${JOBS_URL}/${payload.job_id}/events`;
  return { jobId: payload.job_id, eventsUrl };
};

export const cancelJob = async (jobId: string) => {
  const response = await fetch(`${JOBS_URL}/${jobId}/cancel`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Failed to cancel job.");
  }
  return (await response.json()) as { status?: string };
};

export const fileExists = async (path: string) => {
  const response = await fetch(FS_EXISTS_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path } satisfies FilePathRequest)
  });
  if (!response.ok) {
    throw new Error("Failed to check path.");
  }
  const payload = (await response.json()) as { exists?: boolean };
  return Boolean(payload.exists);
};

export const readTextFile = async (path: string) => {
  const response = await fetch(FS_READ_TEXT_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path } satisfies FilePathRequest)
  });
  if (!response.ok) {
    throw new Error("Failed to read file.");
  }
  const payload = (await response.json()) as { content?: string };
  return payload.content ?? "";
};
