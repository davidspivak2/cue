const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const PROJECTS_URL = `${BACKEND_BASE_URL}/projects`;

export type ActiveTaskChecklistItem = {
  id: string;
  label: string;
  state?: string | null;
  detail?: string | null;
};

export type ActiveTaskSummary = {
  job_id: string;
  kind: string;
  status: string;
  heading?: string | null;
  message?: string | null;
  pct?: number | null;
  step_id?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
  checklist?: ActiveTaskChecklistItem[] | null;
};

export type TaskNotice = {
  notice_id: string;
  project_id?: string | null;
  job_id?: string | null;
  kind?: string | null;
  status: string;
  message: string;
  created_at: string;
  finished_at?: string | null;
};

export type ProjectSummary = {
  project_id: string;
  title: string;
  video_path?: string | null;
  missing_video: boolean;
  status: string;
  created_at: string;
  updated_at: string;
  duration_seconds?: number | null;
  thumbnail_path?: string | null;
  active_task?: ActiveTaskSummary | null;
  task_notice?: TaskNotice | null;
  latest_export?: ProjectLatestExport | null;
};

export type ProjectVideoInfo = {
  path?: string | null;
  filename?: string | null;
  duration_seconds?: number | null;
  thumbnail_path?: string | null;
};

export type ProjectArtifacts = {
  subtitles_path?: string | null;
  word_timings_path?: string | null;
  style_path?: string | null;
};

export type ProjectLatestExport = {
  output_video_path?: string | null;
  exported_at?: string | null;
};

export type ProjectManifest = {
  project_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  video?: ProjectVideoInfo | null;
  artifacts?: ProjectArtifacts | null;
  latest_export?: ProjectLatestExport | null;
  style?: Record<string, unknown> | null;
  active_task?: ActiveTaskSummary | null;
  task_notice?: TaskNotice | null;
};

export type ProjectUpdatePayload = {
  subtitles_srt_text?: string;
  style?: Record<string, unknown>;
};

export type ProjectDeleteResponse = {
  ok: boolean;
  project_id: string;
  cancelled_job_ids?: string[];
};

export type WordTimingWord = {
  text: string;
  start: number;
  end: number;
  confidence?: number | null;
};

export type WordTimingCue = {
  cue_index: number;
  cue_start: number;
  cue_end: number;
  cue_text: string;
  words: WordTimingWord[];
};

export type ProjectWordTimingsDocument = {
  schema_version: number;
  created_utc: string;
  language: string;
  srt_sha256: string;
  cues: WordTimingCue[];
};

export type ProjectWordTimingsResponse = {
  available: boolean;
  stale?: boolean | null;
  reason?: string | null;
  document?: ProjectWordTimingsDocument | null;
  error?: string | null;
};

const ensureOk = async (response: Response) => {
  if (response.ok) {
    return;
  }
  const text = await response.text();
  throw new Error(text || `Request failed: ${response.status}`);
};

export const fetchProjects = async (): Promise<ProjectSummary[]> => {
  const response = await fetch(PROJECTS_URL);
  await ensureOk(response);
  return (await response.json()) as ProjectSummary[];
};

export const createProject = async (videoPath: string): Promise<ProjectSummary> => {
  if (!videoPath) {
    throw new Error("video_path_required");
  }
  const response = await fetch(PROJECTS_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_path: videoPath })
  });
  await ensureOk(response);
  return (await response.json()) as ProjectSummary;
};

export const relinkProject = async (
  projectId: string,
  videoPath: string
): Promise<ProjectSummary> => {
  if (!projectId) {
    throw new Error("project_id_required");
  }
  if (!videoPath) {
    throw new Error("video_path_required");
  }
  const response = await fetch(`${PROJECTS_URL}/${projectId}/relink`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_path: videoPath })
  });
  await ensureOk(response);
  return (await response.json()) as ProjectSummary;
};

export const fetchProject = async (projectId: string): Promise<ProjectManifest> => {
  if (!projectId) {
    throw new Error("project_id_required");
  }
  const response = await fetch(`${PROJECTS_URL}/${projectId}`);
  await ensureOk(response);
  return (await response.json()) as ProjectManifest;
};

export const fetchProjectSubtitles = async (projectId: string): Promise<string> => {
  if (!projectId) {
    throw new Error("project_id_required");
  }
  const response = await fetch(`${PROJECTS_URL}/${projectId}/subtitles`);
  await ensureOk(response);
  const payload = (await response.json()) as { subtitles_srt_text?: unknown };
  if (typeof payload.subtitles_srt_text !== "string") {
    throw new Error("subtitles_srt_text_missing");
  }
  return payload.subtitles_srt_text;
};

export const fetchProjectWordTimings = async (
  projectId: string
): Promise<ProjectWordTimingsResponse> => {
  if (!projectId) {
    throw new Error("project_id_required");
  }
  const response = await fetch(`${PROJECTS_URL}/${projectId}/word-timings`);
  await ensureOk(response);
  return (await response.json()) as ProjectWordTimingsResponse;
};

export const updateProject = async (
  projectId: string,
  payload: ProjectUpdatePayload
): Promise<ProjectManifest> => {
  if (!projectId) {
    throw new Error("project_id_required");
  }
  const response = await fetch(`${PROJECTS_URL}/${projectId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  await ensureOk(response);
  return (await response.json()) as ProjectManifest;
};

export const deleteProject = async (
  projectId: string
): Promise<ProjectDeleteResponse> => {
  if (!projectId) {
    throw new Error("project_id_required");
  }
  const response = await fetch(`${PROJECTS_URL}/${projectId}`, {
    method: "DELETE"
  });
  await ensureOk(response);
  return (await response.json()) as ProjectDeleteResponse;
};
