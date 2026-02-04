import { appDataDir, join, basename } from "@tauri-apps/api/path";
import { nanoid } from "./utils";
import { generateVideoMetadata } from "./videoMetadata";

export type ProjectStatus =
  | "Ready"
  | "Exporting"
  | "Done"
  | "Missing file"
  | "Needs subtitles";

export type Project = {
  projectId: string;
  sourceVideoPath: string;
  filename: string;
  durationSeconds: number;
  thumbnailPath: string;
  status: ProjectStatus;
  lastOpenedAt?: string;
  previousStatus?: ProjectStatus;
};

export type ProjectMap = Record<string, Project>;

const PROJECTS_DIR = "projects";
const STORAGE_KEY = "cue.projects";

const readIndex = async (): Promise<ProjectMap> => {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return {};
  }
  const data = JSON.parse(raw) as ProjectMap;
  return data ?? {};
};

const writeIndex = async (projects: ProjectMap) => {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
};

export const loadProjects = async () => {
  const projects = await readIndex();
  return projects;
};

export const saveProject = async (project: Project) => {
  const projects = await readIndex();
  projects[project.projectId] = project;
  await writeIndex(projects);
};

export const removeProject = async (projectId: string) => {
  const projects = await readIndex();
  delete projects[projectId];
  await writeIndex(projects);
};

export const createProjectFromVideo = async (sourceVideoPath: string) => {
  const projectId = nanoid();
  const dataDir = await appDataDir();
  const projectDir = await join(dataDir, PROJECTS_DIR, projectId);

  const metadata = await generateVideoMetadata(sourceVideoPath, projectDir);
  const project: Project = {
    projectId,
    sourceVideoPath,
    filename: metadata.filename,
    durationSeconds: metadata.durationSeconds,
    thumbnailPath: metadata.thumbnailPath,
    status: "Needs subtitles"
  };
  await saveProject(project);
  return project;
};

export const relinkProject = async (projectId: string, sourceVideoPath: string) => {
  const dataDir = await appDataDir();
  const projectDir = await join(dataDir, PROJECTS_DIR, projectId);
  const metadata = await generateVideoMetadata(sourceVideoPath, projectDir);
  const filename = metadata.filename || (await basename(sourceVideoPath));
  const projects = await readIndex();
  const previous = projects[projectId];
  const restoredStatus =
    previous?.previousStatus && previous.previousStatus !== "Missing file"
      ? previous.previousStatus
      : previous?.status && previous.status !== "Missing file"
        ? previous.status
        : "Needs subtitles";
  const project: Project = {
    projectId,
    sourceVideoPath,
    filename,
    durationSeconds: metadata.durationSeconds,
    thumbnailPath: metadata.thumbnailPath,
    status: restoredStatus,
    previousStatus: undefined
  };
  await saveProject(project);
  return project;
};
