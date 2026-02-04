import { appDataDir, basename, join } from "@tauri-apps/api/path";
import { fileExists, readTextFile, writeTextFile } from "./backendClient";
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
  durationSeconds: number | null;
  thumbnailPath: string;
  status: ProjectStatus;
  createdAt: string;
  lastOpenedAt?: string;
  previousStatus?: ProjectStatus;
};

export type ProjectMap = Record<string, Project>;

const PROJECTS_DIR = "projects";
const PROJECTS_INDEX = "projects.json";

const getIndexPath = async () => {
  const dataDir = await appDataDir();
  return join(dataDir, PROJECTS_DIR, PROJECTS_INDEX);
};

const readIndex = async (): Promise<ProjectMap> => {
  const indexPath = await getIndexPath();
  if (!(await fileExists(indexPath))) {
    return {};
  }
  const raw = await readTextFile(indexPath);
  const data = JSON.parse(raw) as ProjectMap;
  return data ?? {};
};

const writeIndex = async (projects: ProjectMap) => {
  const indexPath = await getIndexPath();
  await writeTextFile(indexPath, JSON.stringify(projects, null, 2));
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
  await join(dataDir, PROJECTS_DIR, projectId);

  const filename = await basename(sourceVideoPath);
  const project: Project = {
    projectId,
    sourceVideoPath,
    filename,
    durationSeconds: null,
    thumbnailPath: "",
    status: "Needs subtitles",
    createdAt: new Date().toISOString()
  };
  await saveProject(project);
  return project;
};

export const updateProjectMetadata = async (project: Project) => {
  const dataDir = await appDataDir();
  const projectDir = await join(dataDir, PROJECTS_DIR, project.projectId);
  const metadata = await generateVideoMetadata(project.sourceVideoPath, projectDir);
  const updated: Project = {
    ...project,
    filename: metadata.filename,
    durationSeconds: metadata.durationSeconds,
    thumbnailPath: metadata.thumbnailPath
  };
  await saveProject(updated);
  return updated;
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
    createdAt: previous?.createdAt ?? new Date().toISOString(),
    previousStatus: undefined
  };
  await saveProject(project);
  return project;
};
