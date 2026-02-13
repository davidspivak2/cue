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
