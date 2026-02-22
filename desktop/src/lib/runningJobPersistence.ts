const KEY = "cue_running_jobs";

export type PersistedRunningJob = {
  jobId: string;
  eventsUrl: string;
  kind: "create_subtitles" | "create_video_with_subtitles";
};

type Stored = Record<string, PersistedRunningJob>;

function load(): Stored {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out: Stored = {};
    for (const [k, v] of Object.entries(parsed)) {
      if (
        typeof k === "string" &&
        v &&
        typeof v === "object" &&
        !Array.isArray(v) &&
        typeof (v as PersistedRunningJob).jobId === "string" &&
        typeof (v as PersistedRunningJob).eventsUrl === "string" &&
        ((v as PersistedRunningJob).kind === "create_subtitles" ||
          (v as PersistedRunningJob).kind === "create_video_with_subtitles")
      ) {
        out[k] = v as PersistedRunningJob;
      }
    }
    return out;
  } catch {
    return {};
  }
}

function save(data: Stored) {
  try {
    localStorage.setItem(KEY, JSON.stringify(data));
  } catch {
    // ignore
  }
}

export function getPersistedRunningJob(projectId: string): PersistedRunningJob | null {
  if (!projectId) return null;
  const data = load();
  return data[projectId] ?? null;
}

export function setPersistedRunningJob(
  projectId: string,
  job: PersistedRunningJob
): void {
  if (!projectId) return;
  const data = load();
  data[projectId] = job;
  save(data);
}

export function clearPersistedRunningJob(projectId: string): void {
  if (!projectId) return;
  const data = load();
  delete data[projectId];
  save(data);
}

export function getAllPersistedProjectIds(): string[] {
  return Object.keys(load());
}
