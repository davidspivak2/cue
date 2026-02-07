const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const JOBS_URL = `${BACKEND_BASE_URL}/jobs`;

export type JobKind = "create_subtitles" | "create_video_with_subtitles";

export type ChecklistStepState = "start" | "done" | "skipped" | "failed";

export type JobEventBase = {
  job_id: string;
  ts: string;
  type: string;
};

export type JobStartedEvent = JobEventBase & {
  type: "started";
  heading?: string;
  message?: string;
  log_path?: string;
  task?: string;
};

export type JobChecklistEvent = JobEventBase & {
  type: "checklist";
  step_id: string;
  state: ChecklistStepState;
  reason_code?: string | null;
  reason_text?: string | null;
};

export type JobProgressEvent = JobEventBase & {
  type: "progress";
  step_id?: string | null;
  step_progress?: number | null;
  pct?: number | null;
  message?: string | null;
};

export type JobLogEvent = JobEventBase & {
  type: "log";
  message: string;
  important?: boolean;
};

export type JobResultPayload = Record<string, unknown>;

export type JobResultEvent = JobEventBase & {
  type: "result";
  payload: JobResultPayload;
};

export type JobHeartbeatEvent = JobEventBase & {
  type: "heartbeat";
};

export type JobCompletedEvent = JobEventBase & {
  type: "completed";
  status?: string;
  message?: string;
  log_path?: string;
};

export type JobCancelledEvent = JobEventBase & {
  type: "cancelled";
  status?: string;
  message?: string;
  log_path?: string;
};

export type JobErrorEvent = JobEventBase & {
  type: "error";
  status?: string;
  message?: string;
  log_path?: string;
  exit_code?: number;
};

export type UnknownJobEvent = JobEventBase & {
  type: string;
  [key: string]: unknown;
};

export type JobEvent =
  | JobStartedEvent
  | JobChecklistEvent
  | JobProgressEvent
  | JobLogEvent
  | JobResultEvent
  | JobHeartbeatEvent
  | JobCompletedEvent
  | JobCancelledEvent
  | JobErrorEvent
  | UnknownJobEvent;

export type JobEventHandlers = {
  onEvent?: (event: JobEvent) => void;
  onOpen?: () => void;
  onError?: (event: Event) => void;
};

export type JobEventStream = {
  jobId: string;
  eventsUrl: string;
  source: EventSource;
  close: () => void;
  cancel: () => Promise<void>;
};

export type JobStartResult = JobEventStream & {
  status: string;
};

export type CreateSubtitlesJobParams = {
  inputPath: string;
  outputDir: string;
  options?: Record<string, unknown>;
};

export type CreateVideoWithSubtitlesJobParams = {
  inputPath: string;
  outputDir: string;
  srtPath: string;
  options?: Record<string, unknown>;
};

type JobRequest = {
  kind: JobKind;
  input_path: string;
  output_dir: string;
  srt_path?: string;
  options?: Record<string, unknown>;
};

type JobCreateResponse = {
  job_id: string;
  events_url: string;
  status: string;
};

const TERMINAL_EVENT_TYPES = new Set(["completed", "cancelled", "error"]);

const ensureOk = async (response: Response) => {
  if (response.ok) {
    return;
  }
  const text = await response.text();
  throw new Error(text || `Request failed: ${response.status}`);
};

const parseJobEvent = (raw: string): JobEvent | null => {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") {
    return null;
  }
  const record = data as Record<string, unknown>;
  if (typeof record.type !== "string") {
    return null;
  }
  return record as JobEvent;
};

const createJob = async (payload: JobRequest): Promise<JobCreateResponse> => {
  const response = await fetch(JOBS_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  await ensureOk(response);
  return (await response.json()) as JobCreateResponse;
};

export const cancelJob = async (jobId: string): Promise<void> => {
  const response = await fetch(`${JOBS_URL}/${jobId}/cancel`, {
    method: "POST"
  });
  await ensureOk(response);
};

const streamJobEvents = (
  jobId: string,
  eventsUrl: string,
  handlers: JobEventHandlers = {}
): JobEventStream => {
  const source = new EventSource(eventsUrl);

  const close = () => {
    source.close();
  };

  const handleMessage = (event: MessageEvent) => {
    const parsed = parseJobEvent(event.data);
    if (!parsed) {
      return;
    }
    handlers.onEvent?.(parsed);
    if (TERMINAL_EVENT_TYPES.has(parsed.type)) {
      source.close();
    }
  };

  source.addEventListener("message", handleMessage);
  source.addEventListener("open", () => handlers.onOpen?.());
  source.addEventListener("error", (event) => handlers.onError?.(event));

  return {
    jobId,
    eventsUrl,
    source,
    close,
    cancel: () => cancelJob(jobId)
  };
};

export const createSubtitlesJob = async (
  params: CreateSubtitlesJobParams,
  handlers: JobEventHandlers = {}
): Promise<JobStartResult> => {
  const job = await createJob({
    kind: "create_subtitles",
    input_path: params.inputPath,
    output_dir: params.outputDir,
    options: params.options ?? {}
  });
  return {
    ...streamJobEvents(job.job_id, job.events_url, handlers),
    status: job.status
  };
};

export const createVideoWithSubtitlesJob = async (
  params: CreateVideoWithSubtitlesJobParams,
  handlers: JobEventHandlers = {}
): Promise<JobStartResult> => {
  const job = await createJob({
    kind: "create_video_with_subtitles",
    input_path: params.inputPath,
    output_dir: params.outputDir,
    srt_path: params.srtPath,
    options: params.options ?? {}
  });
  return {
    ...streamJobEvents(job.job_id, job.events_url, handlers),
    status: job.status
  };
};
