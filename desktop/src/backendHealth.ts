const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const HEALTH_URL = `${BACKEND_BASE_URL}/health`;

type WaitForBackendHealthyOptions = {
  timeoutMs?: number;
  intervalMs?: number;
  requestTimeoutMs?: number;
};

const sleep = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));

const pingBackendHealth = async (requestTimeoutMs: number): Promise<boolean> => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const response = await fetch(HEALTH_URL, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timeoutId);
  }
};

export const waitForBackendHealthy = async (
  options: WaitForBackendHealthyOptions = {}
): Promise<void> => {
  const timeoutMs = options.timeoutMs ?? 60000;
  const intervalMs = options.intervalMs ?? 400;
  const requestTimeoutMs = options.requestTimeoutMs ?? 1500;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    if (await pingBackendHealth(requestTimeoutMs)) {
      return;
    }
    await sleep(intervalMs);
  }

  throw new Error("backend_start_timeout");
};

export const BACKEND_UNREACHABLE_MESSAGE =
  "Cue couldn't start. Try closing and reopening the app.";

export function isBackendUnreachableError(err: unknown): boolean {
  if (err instanceof Error) {
    const msg = err.message.toLowerCase();
    if (msg === "backend_start_timeout") return true;
    if (msg === "failed to fetch") return true;
    if (msg.includes("network") || msg.includes("connection")) return true;
  }
  if (typeof err === "object" && err !== null && "message" in err) {
    const msg = String((err as { message: unknown }).message).toLowerCase();
    if (msg === "failed to fetch") return true;
  }
  return false;
}

export function messageForBackendError(err: unknown, fallback: string): string {
  return isBackendUnreachableError(err) ? BACKEND_UNREACHABLE_MESSAGE : fallback;
}
