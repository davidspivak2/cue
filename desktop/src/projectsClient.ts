const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const PROJECTS_URL = `${BACKEND_BASE_URL}/projects`;

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
