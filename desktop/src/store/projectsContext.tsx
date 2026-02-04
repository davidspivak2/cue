import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { basename, join } from "@tauri-apps/api/path";
import { appDataDir } from "@tauri-apps/api/path";
import { cancelJob, fileExists, JobEvent, readTextFile, startJob } from "./backendClient";
import {
  createProjectFromVideo,
  loadProjects,
  Project,
  ProjectMap,
  relinkProject,
  saveProject,
  updateProjectMetadata
} from "./projects";

type ProjectRuntime = {
  jobId?: string;
  jobStatus: "idle" | "queued" | "running" | "completed" | "cancelled" | "error";
  events: JobEvent[];
  progress: number;
  latestStep?: string;
  startedAt?: number;
  errorMessage?: string;
  errorDetails?: string;
  cancelledAt?: number;
};

type ProjectsContextValue = {
  projects: ProjectMap;
  projectOrder: string[];
  activeTabId?: string;
  openTabs: string[];
  hasActiveJob: boolean;
  activeJobProjectId?: string;
  createProject: (
    sourceVideoPath: string
  ) => Promise<{ project: Project | null; metadataPromise?: Promise<Project> }>;
  openProject: (projectId: string) => void;
  closeProject: (projectId: string) => void;
  relinkProjectPath: (projectId: string, sourceVideoPath: string) => Promise<void>;
  refreshProjects: () => Promise<void>;
  startCreateSubtitles: (projectId: string) => Promise<void>;
  cancelCreateSubtitles: (projectId: string) => Promise<void>;
  getRuntime: (projectId: string) => ProjectRuntime | undefined;
  clearRuntimeError: (projectId: string) => void;
};

const ProjectsContext = createContext<ProjectsContextValue | null>(null);

const wordTimingPathForProject = async (project: Project) => {
  const fileName = await basename(project.sourceVideoPath);
  const stem = fileName.replace(/\.[^/.]+$/, "");
  const dataDir = await appDataDir();
  return join(dataDir, "projects", project.projectId, `${stem}.word_timings.json`);
};

const hasWordTimings = async (project: Project) => {
  const wordTimingPath = await wordTimingPathForProject(project);
  try {
    if (!(await fileExists(wordTimingPath))) {
      return { ok: false, details: "Word timings file is missing." };
    }
    const raw = await readTextFile(wordTimingPath);
    const data = JSON.parse(raw) as { cues?: Array<{ words?: Array<unknown> }> };
    const cues = Array.isArray(data.cues) ? data.cues : [];
    const hasWords = cues.some((cue) => Array.isArray(cue.words) && cue.words.length > 0);
    if (!hasWords) {
      return { ok: false, details: "Word timings file has no words." };
    }
    return { ok: true, details: "" };
  } catch (error) {
    return { ok: false, details: "Word timings file could not be read." };
  }
};

export const ProjectsProvider = ({ children }: { children: React.ReactNode }) => {
  const [projects, setProjects] = useState<ProjectMap>({});
  const [projectOrder, setProjectOrder] = useState<string[]>([]);
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | undefined>(undefined);
  const [runtimes, setRuntimes] = useState<Record<string, ProjectRuntime>>({});
  const eventSourceRef = useRef<Record<string, EventSource | null>>({});

  const refreshProjects = useCallback(async () => {
    let loaded: ProjectMap = {};
    try {
      loaded = await loadProjects();
    } catch (error) {
      console.error(error);
      setProjects({});
      setProjectOrder([]);
      return;
    }
    const ids = Object.keys(loaded);
    const updated: ProjectMap = { ...loaded };
    for (const projectId of ids) {
      const project = loaded[projectId];
      if (!project.createdAt) {
        updated[projectId] = {
          ...project,
          createdAt: new Date().toISOString()
        };
      }
      let videoExists = true;
      try {
        videoExists = await fileExists(project.sourceVideoPath);
      } catch (error) {
        videoExists = true;
      }
      if (!videoExists) {
        if (project.status !== "Missing file") {
          updated[projectId] = {
            ...project,
            previousStatus: project.status,
            status: "Missing file"
          };
        }
      } else if (project.status === "Missing file") {
        const restoredStatus =
          project.previousStatus && project.previousStatus !== "Missing file"
            ? project.previousStatus
            : "Needs subtitles";
        updated[projectId] = {
          ...project,
          status: restoredStatus,
          previousStatus: undefined
        };
      }
    }
    setProjects(updated);
    setProjectOrder(ids);
    await Promise.all(Object.values(updated).map((project) => saveProject(project)));
  }, []);

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  const openProject = useCallback((projectId: string) => {
    setOpenTabs((prev) => (prev.includes(projectId) ? prev : [...prev, projectId]));
    setActiveTabId(projectId);
  }, []);

  const closeProject = useCallback(
    (projectId: string) => {
      setOpenTabs((prev) => {
        const remaining = prev.filter((id) => id !== projectId);
        setActiveTabId((current) => {
          if (current !== projectId) {
            return current;
          }
          return remaining.length ? remaining[0] : undefined;
        });
        return remaining;
      });
    },
    []
  );

  const createProject = useCallback(async (sourceVideoPath: string) => {
    console.log(`createProject: ${sourceVideoPath}`);
    const project = await createProjectFromVideo(sourceVideoPath);
    setProjects((prev) => ({ ...prev, [project.projectId]: project }));
    setProjectOrder((prev) => [...prev, project.projectId]);
    const metadataPromise = updateProjectMetadata(project)
      .then((updated) => {
        setProjects((prev) => ({ ...prev, [project.projectId]: updated }));
        return updated;
      })
      .catch((error: unknown) => {
        console.error(error);
        throw error;
      });
    return { project, metadataPromise };
  }, []);

  const relinkProjectPath = useCallback(async (projectId: string, sourceVideoPath: string) => {
    const project = await relinkProject(projectId, sourceVideoPath);
    setProjects((prev) => ({ ...prev, [project.projectId]: project }));
  }, []);

  const updateRuntime = useCallback((projectId: string, update: Partial<ProjectRuntime>) => {
    setRuntimes((prev) => ({
      ...prev,
      [projectId]: {
        jobStatus: "idle",
        events: [],
        progress: 0,
        ...prev[projectId],
        ...update
      }
    }));
  }, []);

  const closeEventSource = useCallback((projectId: string) => {
    const ref = eventSourceRef.current[projectId];
    if (ref) {
      ref.close();
      eventSourceRef.current[projectId] = null;
    }
  }, []);

  const clearRuntimeError = useCallback(
    (projectId: string) => {
      updateRuntime(projectId, {
        errorMessage: undefined,
        errorDetails: undefined,
        jobStatus: "idle"
      });
    },
    [updateRuntime]
  );

  const startCreateSubtitles = useCallback(
    async (projectId: string) => {
      const project = projects[projectId];
      if (!project) {
        return;
      }
      updateRuntime(projectId, {
        jobStatus: "queued",
        events: [],
        progress: 0,
        latestStep: undefined,
        startedAt: Date.now(),
        cancelledAt: undefined,
        errorMessage: undefined,
        errorDetails: undefined
      });
      try {
        const dataDir = await appDataDir();
        const outputDir = await join(dataDir, "projects", projectId);
        const { jobId, eventsUrl } = await startJob({
          kind: "pipeline",
          input_path: project.sourceVideoPath,
          output_dir: outputDir,
          options: {}
        });
        updateRuntime(projectId, { jobId, jobStatus: "running" });

        const source = new EventSource(eventsUrl);
        eventSourceRef.current[projectId] = source;

        source.onmessage = async (messageEvent) => {
          try {
            const event = JSON.parse(messageEvent.data) as JobEvent;
            setRuntimes((prev) => {
              const current = prev[projectId] ?? {
                jobStatus: "running",
                events: [],
                progress: 0
              };
              const events = [...current.events, event].slice(-200);
              const next: ProjectRuntime = { ...current, events };
              if (event.type === "step" && event.step) {
                next.latestStep = event.step;
              }
              if (event.type === "progress" && typeof event.pct === "number") {
                next.progress = event.pct;
              }
              if (event.type === "started") {
                next.jobStatus = "running";
              }
              if (event.type === "cancelled") {
                next.jobStatus = "cancelled";
                next.cancelledAt = Date.now();
              }
              if (event.type === "error") {
                next.jobStatus = "error";
                next.errorMessage = event.message ?? "Job failed.";
                next.errorDetails = event.message ?? "Job failed.";
              }
              if (event.type === "completed") {
                next.jobStatus = "completed";
              }
              return { ...prev, [projectId]: next };
            });
            if (event.type === "completed") {
              closeEventSource(projectId);
              const result = await hasWordTimings(project);
              if (result.ok) {
                const updatedProject: Project = {
                  ...project,
                  status: "Ready"
                };
                await saveProject(updatedProject);
                setProjects((prev) => ({ ...prev, [projectId]: updatedProject }));
                updateRuntime(projectId, { jobStatus: "idle" });
              } else {
                updateRuntime(projectId, {
                  jobStatus: "error",
                  errorMessage: "Subtitles creation failed.",
                  errorDetails: result.details
                });
              }
            }
            if (event.type === "cancelled") {
              closeEventSource(projectId);
              updateRuntime(projectId, { jobStatus: "idle" });
            }
            if (event.type === "error") {
              closeEventSource(projectId);
            }
          } catch (error) {
            updateRuntime(projectId, {
              jobStatus: "error",
              errorMessage: "Failed to parse event stream message.",
              errorDetails: "Failed to parse event stream message."
            });
            closeEventSource(projectId);
          }
        };

        source.onerror = () => {
          updateRuntime(projectId, {
            jobStatus: "error",
            errorMessage: "Connection lost.",
            errorDetails: "Connection lost."
          });
          closeEventSource(projectId);
        };
      } catch (error) {
        updateRuntime(projectId, {
          jobStatus: "error",
          errorMessage: "Failed to start job.",
          errorDetails: "Failed to start job."
        });
      }
    },
    [closeEventSource, projects, updateRuntime]
  );

  const cancelCreateSubtitles = useCallback(
    async (projectId: string) => {
      const runtime = runtimes[projectId];
      if (!runtime?.jobId) {
        return;
      }
      try {
        await cancelJob(runtime.jobId);
      } catch (error) {
        updateRuntime(projectId, {
          jobStatus: "error",
          errorMessage: "Failed to cancel job.",
          errorDetails: "Failed to cancel job."
        });
      }
    },
    [runtimes, updateRuntime]
  );

  const getRuntime = useCallback(
    (projectId: string) => {
      return runtimes[projectId];
    },
    [runtimes]
  );

  const hasActiveJob = useMemo(() => {
    return Object.values(runtimes).some((runtime) =>
      ["queued", "running"].includes(runtime.jobStatus)
    );
  }, [runtimes]);

  const activeJobProjectId = useMemo(() => {
    const entry = Object.entries(runtimes).find(([, runtime]) =>
      ["queued", "running"].includes(runtime.jobStatus)
    );
    return entry?.[0];
  }, [runtimes]);

  const value = useMemo(
    () => ({
      projects,
      projectOrder,
      activeTabId,
      openTabs,
      hasActiveJob,
      activeJobProjectId,
      openProject,
      closeProject,
      createProject,
      relinkProjectPath,
      refreshProjects,
      startCreateSubtitles,
      cancelCreateSubtitles,
      getRuntime,
      clearRuntimeError
    }),
    [
      projects,
      projectOrder,
      activeTabId,
      openTabs,
      hasActiveJob,
      activeJobProjectId,
      openProject,
      closeProject,
      createProject,
      relinkProjectPath,
      refreshProjects,
      startCreateSubtitles,
      cancelCreateSubtitles,
      getRuntime,
      clearRuntimeError
    ]
  );

  return <ProjectsContext.Provider value={value}>{children}</ProjectsContext.Provider>;
};

export const useProjects = () => {
  const context = useContext(ProjectsContext);
  if (!context) {
    throw new Error("useProjects must be used within ProjectsProvider");
  }
  return context;
};
