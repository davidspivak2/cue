import * as React from "react";
import { LayoutGrid, List, Trash2, Upload, X } from "lucide-react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { useLocation, useNavigate } from "react-router-dom";

import EngineSkeletonLoader from "@/components/EngineSkeletonLoader";
import PageHeader from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useSettings } from "@/contexts/SettingsContext";
import { useToast } from "@/contexts/ToastContext";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "@/components/ui/tooltip";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  clearPersistedRunningJob,
  getPersistedRunningJob,
  type PersistedRunningJob
} from "@/lib/runningJobPersistence";
import { resolveLocalFileUrl } from "@/lib/localFileUrl";
import { cn } from "@/lib/utils";
import {
  type ActiveTaskSummary,
  createProject,
  createProjectFromFile,
  deleteProject,
  fetchProjects,
  type ProjectSummary,
  relinkProject,
  relinkProjectFromFile
} from "@/projectsClient";
import { useWorkbenchTabs } from "@/workbenchTabs";
import {
  BACKEND_UNREACHABLE_MESSAGE,
  isBackendUnreachableError,
  waitForBackendHealthy
} from "@/backendHealth";

type FileWithPath = File & { path?: string };

type BannerTone = "info" | "error";

type Banner = {
  type: BannerTone;
  message: string;
};

type RelinkWarning = {
  project: ProjectSummary;
  selection: RelinkSelection;
  reasons: string[];
};

type RelinkSelection = {
  file?: File;
  fileName: string;
  path?: string;
  duration: number | null;
};

type ProjectHubLocationState = {
  cancelledCreateProjectId?: string;
  cancelledCreateProjectTitle?: string;
} | null;

const STATUS_LABELS: Record<string, string> = {
  ready: "Ready to review",
  exporting: "Exporting",
  done: "Exported",
  missing_file: "Missing file",
  needs_video: "Missing file",
  needs_subtitles: "Not started"
};

const SUPPORTED_EXTENSIONS = new Set(["mp4", "mkv", "mov", "m4v", "webm"]);
const UNSUPPORTED_VIDEO_TYPE_MESSAGE =
  "Unsupported file type. Choose MP4, MKV, MOV, M4V, or WEBM.";
const MAX_DURATION_DIFF_SECONDS = 3;
const HAS_HAD_VIDEOS_KEY = "cue_has_had_videos";
const PROJECT_HUB_VIEW_KEY = "cue_project_hub_view";
const PROJECT_HUB_LAST_COUNT_KEY = "cue_project_hub_last_count";
const ADD_VIDEO_BUTTON = "Add video";
const REMOVE_FROM_CUE_LABEL = "Remove from Cue";
const PROJECT_LIST_ACTIONS_COLUMN_WIDTH = "3.75rem";
const PROJECT_LIST_DATA_COLUMN_WIDTH =
  `calc((100% - ${PROJECT_LIST_ACTIONS_COLUMN_WIDTH}) / 4)`;

type ViewMode = "cards" | "list";

const isValidViewMode = (v: string): v is ViewMode =>
  v === "cards" || v === "list";
const EMPTY_WELCOME_LEAD = "Hello 👋";
const EMPTY_WELCOME_REST =
  " Cue adds subtitles to your videos using OpenAI's Whisper speech recognition.";
const EMPTY_MAIN = "Drop a video here or click to browse to generate subtitles.";
const EMPTY_SUPPORTED_FORMATS = "Supports MP4, MKV, MOV, M4V, WEBM.";
const ACTIVE_TASK_POLL_MS = 2500;
const IDLE_TASK_POLL_MS = 10000;

const formatDuration = (durationSeconds?: number | null) => {
  if (durationSeconds === null || durationSeconds === undefined) {
    return "";
  }
  if (Number.isNaN(durationSeconds)) {
    return "";
  }
  const totalSeconds = Math.max(0, Math.floor(durationSeconds));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
};

const resolveFilePath = (file: File) => {
  const withPath = file as FileWithPath;
  return withPath.path ?? "";
};

const getFileName = (value: string) => {
  const parts = value.split(/[/\\]/);
  return parts[parts.length - 1] ?? value;
};

const resolveProjectTitle = (project: ProjectSummary) => {
  if (project.title) {
    return project.title;
  }
  if (project.video_path) {
    return getFileName(project.video_path);
  }
  return "Untitled video";
};

const MAX_TOAST_NAME_LENGTH = 50;

const truncateForToast = (name: string, maxLen = MAX_TOAST_NAME_LENGTH): string => {
  if (name.length <= maxLen) return name;
  const trimmed = name.slice(0, maxLen - 1).trim();
  return trimmed.length > 0 ? `${trimmed}\u2026` : name.slice(0, maxLen);
};

const getFileExtension = (value: string) => {
  const name = getFileName(value);
  const index = name.lastIndexOf(".");
  if (index === -1) {
    return "";
  }
  return name.slice(index + 1).toLowerCase();
};

const isSupportedVideo = (value: string) => SUPPORTED_EXTENSIONS.has(getFileExtension(value));

const getVideoDurationFromFile = (file: File): Promise<number | null> =>
  new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");

    const cleanup = () => {
      URL.revokeObjectURL(url);
      video.removeAttribute("src");
      video.load();
    };

    video.preload = "metadata";
    video.onloadedmetadata = () => {
      const duration = Number.isFinite(video.duration) ? video.duration : null;
      cleanup();
      resolve(duration);
    };
    video.onerror = () => {
      cleanup();
      resolve(null);
    };
    video.src = url;
  });

const getVideoDurationFromPath = (path: string, useTauri: boolean): Promise<number | null> =>
  new Promise((resolve) => {
    const video = document.createElement("video");
    const src = resolveLocalFileUrl(path, useTauri);

    const cleanup = () => {
      video.removeAttribute("src");
      video.load();
    };

    video.preload = "metadata";
    video.onloadedmetadata = () => {
      const duration = Number.isFinite(video.duration) ? video.duration : null;
      cleanup();
      resolve(duration);
    };
    video.onerror = () => {
      cleanup();
      resolve(null);
    };
    video.src = src;
  });

const resolveStatusLabel = (project: ProjectSummary) => {
  if (project.missing_video) {
    return "Missing file";
  }
  const task = project.active_task;
  if (task?.status === "queued") {
    return "Queued";
  }
  if (task?.kind === "create_subtitles") {
    return "Creating subtitles";
  }
  if (task?.kind === "create_video_with_subtitles") {
    return "Exporting";
  }
  return STATUS_LABELS[project.status] ?? "Not started";
};

const resolveStatusBadgeClassName = (project: ProjectSummary): string => {
  if (project.missing_video) {
    return "border-transparent bg-red-500/15 text-red-700 dark:bg-red-400/20 dark:text-red-300";
  }
  if (project.active_task?.status === "queued") {
    return "border-transparent bg-slate-500/15 text-slate-600 dark:bg-slate-400/20 dark:text-slate-300";
  }
  const taskKind = project.active_task?.kind;
  if (taskKind === "create_subtitles" || taskKind === "create_video_with_subtitles") {
    return "border-transparent bg-amber-500/15 text-amber-700 dark:bg-amber-400/20 dark:text-amber-300";
  }
  const status = project.status ?? "";
  switch (status) {
    case "ready":
      return "border-transparent bg-emerald-500/15 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-300";
    case "exporting":
      return "border-transparent bg-amber-500/15 text-amber-700 dark:bg-amber-400/20 dark:text-amber-300";
    case "done":
      return "border-transparent bg-blue-500/15 text-blue-700 dark:bg-blue-400/20 dark:text-blue-300";
    case "missing_file":
    case "needs_video":
      return "border-transparent bg-red-500/15 text-red-700 dark:bg-red-400/20 dark:text-red-300";
    case "needs_subtitles":
    default:
      return "border-transparent bg-slate-500/15 text-slate-600 dark:bg-slate-400/20 dark:text-slate-300";
  }
};

const resolveThumbnailSrc = (path: string | null | undefined, useTauri: boolean) => {
  return resolveLocalFileUrl(path, useTauri);
};

const resolveTaskHeading = (project: ProjectSummary) => {
  if (project.active_task?.status === "queued") {
    return "Queued";
  }
  const heading = project.active_task?.heading;
  if (typeof heading === "string" && heading.trim()) {
    return heading;
  }
  if (project.active_task?.kind === "create_video_with_subtitles") {
    return "Exporting video";
  }
  return "Creating subtitles";
};

const withPersistedActiveTask = (
  project: ProjectSummary,
  persistedJob: PersistedRunningJob | null
): ProjectSummary => {
  if (project.active_task) {
    return project;
  }
  if (persistedJob?.kind !== "create_subtitles" || project.status !== "needs_subtitles") {
    return project;
  }
  const activeTask: ActiveTaskSummary = {
    job_id: persistedJob.jobId,
    kind: "create_subtitles",
    status: "running",
    pct: 0,
    heading: "Creating subtitles",
    message: null
  };
  return { ...project, active_task: activeTask };
};

const ProjectHub = () => {
  const location = useLocation();
  const incomingState = location.state as ProjectHubLocationState;
  const navigate = useNavigate();
  const { openSettings } = useSettings();
  const { pushToast } = useToast();
  const { closeTab, ensureTab, openOrActivateTab } = useWorkbenchTabs();
  const [projects, setProjects] = React.useState<ProjectSummary[]>([]);
  const [optimisticallyHiddenProjectIds, setOptimisticallyHiddenProjectIds] =
    React.useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = React.useState(true);
  const [, setIsBackendStarting] = React.useState(true);
  const [banner, setBanner] = React.useState<Banner | null>(null);
  const [isDragging, setIsDragging] = React.useState(false);
  const [isCreating, setIsCreating] = React.useState(false);
  const [relinkPromptProject, setRelinkPromptProject] = React.useState<ProjectSummary | null>(
    null
  );
  const [relinkWarning, setRelinkWarning] = React.useState<RelinkWarning | null>(null);
  const [deleteConfirmProject, setDeleteConfirmProject] =
    React.useState<ProjectSummary | null>(null);
  const [pendingRelinkProject, setPendingRelinkProject] = React.useState<ProjectSummary | null>(
    null
  );
  const [busyProjectId, setBusyProjectId] = React.useState<string | null>(null);
  const [deletingProjectId, setDeletingProjectId] = React.useState<string | null>(null);
  const [dismissedNoticeIds, setDismissedNoticeIds] = React.useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = React.useState<ViewMode>(() => {
    if (typeof window === "undefined") return "cards";
    const stored = localStorage.getItem(PROJECT_HUB_VIEW_KEY);
    return stored && isValidViewMode(stored) ? stored : "cards";
  });
  React.useEffect(() => {
    try {
      localStorage.setItem(PROJECT_HUB_VIEW_KEY, viewMode);
    } catch {
      /* ignore */
    }
  }, [viewMode]);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const relinkInputRef = React.useRef<HTMLInputElement>(null);
  const handledCreateCancelKeyRef = React.useRef<string | null>(null);

  const isTauriEnv = isTauri();
  const isRelinking = busyProjectId !== null;
  const isDeleting = deletingProjectId !== null;
  const isBusyOperation = isRelinking || isDeleting;

  const showBanner = React.useCallback((type: BannerTone, message: string) => {
    setBanner({ type, message });
  }, []);

  const hideProjectOptimistically = React.useCallback((projectId: string) => {
    if (!projectId) {
      return;
    }
    setOptimisticallyHiddenProjectIds((prev) => {
      if (prev.has(projectId)) {
        return prev;
      }
      const next = new Set(prev);
      next.add(projectId);
      return next;
    });
  }, []);

  const unhideProjectOptimistically = React.useCallback((projectId: string) => {
    if (!projectId) {
      return;
    }
    setOptimisticallyHiddenProjectIds((prev) => {
      if (!prev.has(projectId)) {
        return prev;
      }
      const next = new Set(prev);
      next.delete(projectId);
      return next;
    });
  }, []);

  const loadProjects = React.useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true;
    if (!silent) {
      setIsLoading(true);
    }
    setIsBackendStarting(true);
    try {
      await waitForBackendHealthy();
      setIsBackendStarting(false);
      const data = await fetchProjects();
      data.forEach((p) => {
        if (p.status === "ready" && getPersistedRunningJob(p.project_id)?.kind === "create_subtitles") {
          clearPersistedRunningJob(p.project_id);
        }
      });
      setProjects(data);
      try {
        localStorage.setItem(PROJECT_HUB_LAST_COUNT_KEY, String(data.length));
        if (data.length > 0) {
          localStorage.setItem(HAS_HAD_VIDEOS_KEY, "true");
        }
      } catch {
        /* ignore */
      }
    } catch (err) {
      setBanner({
        type: "error",
        message: isBackendUnreachableError(err)
          ? BACKEND_UNREACHABLE_MESSAGE
          : err instanceof Error
            ? err.message
            : "Failed to load videos."
      });
    } finally {
      setIsBackendStarting(false);
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const prevPathRef = React.useRef<string>(location.pathname);
  React.useEffect(() => {
    const isOnHub = location.pathname === "/";
    const wasElsewhere = prevPathRef.current !== "/";
    prevPathRef.current = location.pathname;
    if (isOnHub && wasElsewhere && !isLoading) {
      const t = window.setTimeout(() => {
        void loadProjects({ silent: true });
      }, 300);
      return () => clearTimeout(t);
    }
  }, [location.pathname, loadProjects, isLoading]);

  React.useEffect(() => {
    const cancelledCreateProjectId =
      typeof incomingState?.cancelledCreateProjectId === "string"
        ? incomingState.cancelledCreateProjectId
        : "";
    if (!cancelledCreateProjectId) {
      return;
    }
    if (handledCreateCancelKeyRef.current === location.key) {
      return;
    }
    handledCreateCancelKeyRef.current = location.key;

    hideProjectOptimistically(cancelledCreateProjectId);
    window.history.replaceState({}, "");

    void deleteProject(cancelledCreateProjectId)
      .then(() => {
        setProjects((prev) =>
          prev.filter((entry) => entry.project_id !== cancelledCreateProjectId)
        );
        unhideProjectOptimistically(cancelledCreateProjectId);
        closeTab(cancelledCreateProjectId);
      })
      .catch((err) => {
        unhideProjectOptimistically(cancelledCreateProjectId);
        showBanner(
          "error",
          err instanceof Error
            ? err.message
            : "Failed to remove cancelled video. Please try deleting it again."
        );
      });
  }, [
    closeTab,
    hideProjectOptimistically,
    incomingState,
    location.key,
    showBanner,
    unhideProjectOptimistically
  ]);

  React.useEffect(() => {
    if (isLoading) {
      return;
    }
    let cancelled = false;
    const hasAnyActiveTask =
      projects.some((project) => Boolean(project.active_task)) ||
      projects.some(
        (project) => getPersistedRunningJob(project.project_id)?.kind === "create_subtitles"
      );
    const pollDelay =
      hasAnyActiveTask || projects.length > 0 ? ACTIVE_TASK_POLL_MS : IDLE_TASK_POLL_MS;
    const timer = window.setTimeout(async () => {
      try {
        const data = await fetchProjects();
        if (!cancelled) {
          data.forEach((p) => {
            if (p.status === "ready" && getPersistedRunningJob(p.project_id)?.kind === "create_subtitles") {
              clearPersistedRunningJob(p.project_id);
            }
          });
          setProjects(data);
          try {
            localStorage.setItem(PROJECT_HUB_LAST_COUNT_KEY, String(data.length));
            if (data.length > 0) {
              localStorage.setItem(HAS_HAD_VIDEOS_KEY, "true");
            }
          } catch {
            /* ignore */
          }
        }
      } catch {
        // Best-effort background polling only.
      }
    }, pollDelay);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [isLoading, projects]);

  const handleCreateProject = React.useCallback(
    async (videoPath: string) => {
      if (!videoPath) {
        showBanner("error", "Could not read this file path. Please try a different file.");
        return;
      }
      if (!isSupportedVideo(videoPath)) {
        showBanner("error", UNSUPPORTED_VIDEO_TYPE_MESSAGE);
        return;
      }
      setBanner(null);
      setIsCreating(true);
      try {
        const createdProject = await createProject(videoPath);
        await loadProjects();
        openOrActivateTab({
          projectId: createdProject.project_id,
          title: resolveProjectTitle(createdProject),
          path: createdProject.video_path ?? undefined,
          thumbnail_path: createdProject.thumbnail_path ?? undefined
        });
        navigate(`/workbench/${encodeURIComponent(createdProject.project_id)}`, {
          state: { autoStartSubtitles: true }
        });
      } catch (err) {
        showBanner("error", err instanceof Error ? err.message : "Failed to create video.");
      } finally {
        setIsCreating(false);
      }
    },
    [loadProjects, navigate, openOrActivateTab, showBanner]
  );

  const handleCreateProjectFromBrowserFile = React.useCallback(
    async (file: File) => {
      setBanner(null);
      setIsCreating(true);
      try {
        const createdProject = await createProjectFromFile(file);
        await loadProjects();
        openOrActivateTab({
          projectId: createdProject.project_id,
          title: resolveProjectTitle(createdProject),
          path: createdProject.video_path ?? undefined,
          thumbnail_path: createdProject.thumbnail_path ?? undefined
        });
        navigate(`/workbench/${encodeURIComponent(createdProject.project_id)}`, {
          state: { autoStartSubtitles: true }
        });
      } catch (err) {
        showBanner("error", err instanceof Error ? err.message : "Failed to create video.");
      } finally {
        setIsCreating(false);
      }
    },
    [loadProjects, navigate, openOrActivateTab, showBanner]
  );

  const handleFileSelected = React.useCallback(
    async (file: File) => {
      const resolvedPath = resolveFilePath(file);
      if (resolvedPath) {
        await handleCreateProject(resolvedPath);
        return;
      }
      if (!isTauriEnv) {
        await handleCreateProjectFromBrowserFile(file);
        return;
      }
      showBanner("error", "Could not read this file path. Please try a different file.");
    },
    [handleCreateProject, handleCreateProjectFromBrowserFile, isTauriEnv, showBanner]
  );

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      void handleFileSelected(file);
    }
    event.target.value = "";
  };

  const openFileDialog = React.useCallback(async () => {
    if (isCreating || isBusyOperation) {
      return;
    }
    if (!isTauriEnv) {
      inputRef.current?.click();
      return;
    }
    try {
      const selected = await openDialog({
        multiple: false,
        directory: false,
        filters: [
          {
            name: "Video files",
            extensions: ["mp4", "mkv", "mov", "m4v", "webm"]
          }
        ],
        pickerMode: "video"
      });
      if (typeof selected === "string" && selected) {
        await handleCreateProject(selected);
      }
    } catch {
      showBanner("error", "Could not open the file picker. Please try again.");
    }
  }, [handleCreateProject, isBusyOperation, isCreating, isTauriEnv, showBanner]);

  const emptyStateZoneRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!isTauriEnv) {
      return;
    }
    let unlisten: (() => void) | null = null;
    getCurrentWebview()
      .onDragDropEvent((event) => {
        const payload = event.payload as {
          type: string;
          position?: { x: number; y: number };
          paths?: string[];
        };
        if (payload.type === "enter") {
          setIsDragging(false);
          return;
        }
        if (payload.type === "over") {
          const zone = emptyStateZoneRef.current;
          const pos = payload.position;
          if (zone && pos != null && typeof pos.x === "number" && typeof pos.y === "number") {
            const rect = zone.getBoundingClientRect();
            const scale = 1 / (typeof window !== "undefined" ? window.devicePixelRatio : 1);
            const x = pos.x * scale;
            const y = pos.y * scale;
            const inZone =
              x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
            setIsDragging(inZone);
          } else {
            setIsDragging(false);
          }
          return;
        }
        if (payload.type === "drop" || payload.type === "leave") {
          setIsDragging(false);
        }
        if (payload.type !== "drop") {
          return;
        }
        const [path] = payload.paths ?? [];
        if (path) {
          handleCreateProject(path);
        }
      })
      .then((stop) => {
        unlisten = stop;
      })
      .catch(() => {});
    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, [handleCreateProject, isTauriEnv]);

  const handleDragEnter = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (isCreating || isBusyOperation) {
      return;
    }
    setIsDragging(true);
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (isCreating || isBusyOperation) {
      return;
    }
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    if (isCreating || isBusyOperation) {
      return;
    }
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (isCreating || isBusyOperation) {
      return;
    }
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) {
      void handleFileSelected(file);
    }
  };

  const buildRelinkWarnings = (
    project: ProjectSummary,
    selectedFileName: string,
    selectedDuration: number | null
  ) => {
    const warnings: string[] = [];
    const originalNameSource = project.video_path || project.title || "";
    const originalFileName = originalNameSource ? getFileName(originalNameSource) : "";
    if (
      originalFileName &&
      selectedFileName &&
      originalFileName.toLowerCase() !== selectedFileName.toLowerCase()
    ) {
      warnings.push(`Filename does not match (${originalFileName}).`);
    }
    if (
      selectedDuration !== null &&
      project.duration_seconds !== null &&
      project.duration_seconds !== undefined
    ) {
      const diffSeconds = Math.abs(project.duration_seconds - selectedDuration);
      if (diffSeconds > MAX_DURATION_DIFF_SECONDS) {
        warnings.push(`Duration differs by about ${Math.round(diffSeconds)} seconds.`);
      }
    }
    return warnings;
  };

  const performRelink = React.useCallback(
    async (project: ProjectSummary, selection: RelinkSelection) => {
      setBanner(null);
      setBusyProjectId(project.project_id);
      try {
        if (selection.path) {
          await relinkProject(project.project_id, selection.path);
        } else if (selection.file) {
          await relinkProjectFromFile(project.project_id, selection.file);
        } else {
          throw new Error("video_path_required");
        }
        await loadProjects();
        showBanner("info", "Video relinked.");
      } catch (err) {
        showBanner("error", err instanceof Error ? err.message : "Failed to relink the video.");
      } finally {
        setBusyProjectId(null);
      }
    },
    [loadProjects, showBanner]
  );

  const handleRelinkSelection = React.useCallback(
    async (
      project: ProjectSummary,
      selection: RelinkSelection
    ) => {
      if (!isSupportedVideo(selection.fileName)) {
        showBanner("error", UNSUPPORTED_VIDEO_TYPE_MESSAGE);
        return;
      }
      const warnings = buildRelinkWarnings(project, selection.fileName, selection.duration);
      if (warnings.length > 0) {
        setRelinkWarning({ project, selection, reasons: warnings });
        return;
      }
      await performRelink(project, selection);
    },
    [performRelink, showBanner]
  );

  const beginRelinkSelection = React.useCallback(
    async (project: ProjectSummary) => {
      if (isBusyOperation) {
        return;
      }
      setRelinkPromptProject(null);
      setBanner(null);
      if (isTauriEnv) {
        try {
          const selected = await openDialog({
            multiple: false,
            directory: false,
            filters: [
              {
                name: "Video files",
                extensions: ["mp4", "mkv", "mov", "m4v", "webm"]
              }
            ],
            pickerMode: "video"
          });
          if (typeof selected === "string" && selected) {
            const duration = await getVideoDurationFromPath(selected, isTauriEnv);
            await handleRelinkSelection(project, {
              path: selected,
              fileName: getFileName(selected),
              duration
            });
          }
        } catch {
          // Fall back to file input when native dialog is unavailable (e.g. in e2e tests)
          setPendingRelinkProject(project);
          relinkInputRef.current?.click();
        }
        return;
      }
      setPendingRelinkProject(project);
      relinkInputRef.current?.click();
    },
    [handleRelinkSelection, isBusyOperation, isTauriEnv]
  );

  const handleRelinkInputChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    const project = pendingRelinkProject;
    setPendingRelinkProject(null);
    if (!project) {
      return;
    }
    const duration = await getVideoDurationFromFile(file);
    const resolvedPath = resolveFilePath(file);
    await handleRelinkSelection(project, {
      file,
      fileName: file.name,
      path: resolvedPath || undefined,
      duration
    });
  };

  const openProjectTab = (project: ProjectSummary, inNewTab: boolean) => {
    if (project.missing_video || project.status === "missing_file") {
      if (!inNewTab) setRelinkPromptProject(project);
      return;
    }
    const tab = {
      projectId: project.project_id,
      title: resolveProjectTitle(project),
      path: project.video_path ?? undefined,
      thumbnail_path: project.thumbnail_path ?? undefined
    };
    if (inNewTab) {
      ensureTab(tab);
    } else {
      openOrActivateTab(tab);
      navigate(`/workbench/${encodeURIComponent(project.project_id)}`);
    }
  };

  const handleCardClick = (event: React.MouseEvent, project: ProjectSummary) => {
    if (isBusyOperation) return;
    const inNewTab = event.button === 1 || event.ctrlKey || event.metaKey;
    event.preventDefault();
    openProjectTab(project, inNewTab);
  };

  const handleCardAuxClick = (event: React.MouseEvent, project: ProjectSummary) => {
    if (event.button === 1) {
      event.preventDefault();
      if (!isBusyOperation) openProjectTab(project, true);
    }
  };

  const confirmRelinkWarning = async () => {
    if (!relinkWarning) {
      return;
    }
    const { project, selection } = relinkWarning;
    setRelinkWarning(null);
    await performRelink(project, selection);
  };

  const confirmDeleteProject = React.useCallback(async () => {
    if (!deleteConfirmProject || isBusyOperation) {
      return;
    }
    const project = deleteConfirmProject;
    setDeleteConfirmProject(null);
    setBanner(null);
    setDeletingProjectId(project.project_id);
    try {
      await deleteProject(project.project_id);
      setProjects((prev) => prev.filter((entry) => entry.project_id !== project.project_id));
      closeTab(project.project_id);
      const displayName =
        truncateForToast(resolveProjectTitle(project).trim()) || "The video";
      pushToast(`${displayName} removed from Cue.`, "");
    } catch (err) {
      showBanner(
        "error",
        err instanceof Error ? err.message : "Failed to remove video from Cue."
      );
    } finally {
      setDeletingProjectId(null);
    }
  }, [closeTab, deleteConfirmProject, isBusyOperation, pushToast, showBanner]);

  const visibleProjects = React.useMemo(
    () =>
      projects.filter((project) => !optimisticallyHiddenProjectIds.has(project.project_id)),
    [optimisticallyHiddenProjectIds, projects]
  );
  const skeletonProjectCount = React.useMemo(() => {
    if (visibleProjects.length > 0) return visibleProjects.length;
    try {
      const s = localStorage.getItem(PROJECT_HUB_LAST_COUNT_KEY);
      if (s == null) return undefined;
      const n = parseInt(s, 10);
      return Number.isInteger(n) && n >= 0 ? n : undefined;
    } catch {
      return undefined;
    }
  }, [visibleProjects.length]);
  const showEmptyState = !isLoading && visibleProjects.length === 0;
  const isBackendUnreachable =
    banner?.type === "error" && banner?.message === BACKEND_UNREACHABLE_MESSAGE;
  const enableRootDrop = !isTauriEnv && !isBusyOperation;

  const dismissTaskNotice = (noticeId: string) => {
    setDismissedNoticeIds((prev) => {
      const next = new Set(prev);
      next.add(noticeId);
      return next;
    });
  };

  const handleRootDragOver = React.useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  }, []);

  return (
    <TooltipProvider delayDuration={300}>
      <div
        data-testid="project-hub"
        className="space-y-6 rounded-lg border border-transparent"
        onDragOver={enableRootDrop ? handleRootDragOver : undefined}
        onDrop={enableRootDrop ? handleDrop : undefined}
      >
      {!showEmptyState && (
        <PageHeader
          title={<h1 className="text-lg font-semibold tracking-tight text-foreground">Home</h1>}
          onOpenSettings={openSettings}
          showSettings={!isTauriEnv}
          right={
            <>
              {visibleProjects.length > 0 && (
                <ToggleGroup
                  type="single"
                  variant="outline"
                  value={viewMode}
                  onValueChange={(v) => v && isValidViewMode(v) && setViewMode(v)}
                  className="inline-flex [&_[data-slot=toggle-group-item]]:h-8"
                >
                  <ToggleGroupItem value="cards" aria-label="Card view" className="relative">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span
                          className="absolute inset-0 rounded-[inherit]"
                          onClick={(e) => (e.target as HTMLElement).closest("button")?.click()}
                        />
                      </TooltipTrigger>
                      <TooltipContent side="top" sideOffset={4}>Card view</TooltipContent>
                    </Tooltip>
                    <LayoutGrid className="relative z-10 h-4 w-4" />
                  </ToggleGroupItem>
                  <ToggleGroupItem value="list" aria-label="List view" className="relative">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span
                          className="absolute inset-0 rounded-[inherit]"
                          onClick={(e) => (e.target as HTMLElement).closest("button")?.click()}
                        />
                      </TooltipTrigger>
                      <TooltipContent side="top" sideOffset={4}>List view</TooltipContent>
                    </Tooltip>
                    <List className="relative z-10 h-4 w-4" />
                  </ToggleGroupItem>
                </ToggleGroup>
              )}
              <Button size="sm" onClick={openFileDialog} disabled={isCreating || isBusyOperation}>
                {ADD_VIDEO_BUTTON}
              </Button>
            </>
          }
        />
      )}

      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={handleInputChange}
        disabled={isCreating || isBusyOperation}
        data-testid="new-project-input"
      />

      <input
        ref={relinkInputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={handleRelinkInputChange}
        disabled={isBusyOperation}
        data-testid="relink-input"
      />

      {banner && !isBackendUnreachable && (
        <div
          data-testid="project-hub-banner"
          className={cn(
            "flex items-start justify-between gap-3 rounded-md border p-3 text-sm",
            banner.type === "error"
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : "border-border bg-card text-foreground"
          )}
        >
          <span>{banner.message}</span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setBanner(null)}
            aria-label="Dismiss message"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}

      {isLoading && !isBackendUnreachable && (
                <EngineSkeletonLoader
                  variant="hub"
                  hubView={viewMode}
                  projectCount={skeletonProjectCount}
                />
              )}

      {isBackendUnreachable && (
        <div
          className="flex min-h-[calc(100vh-8rem)] flex-1 flex-col items-center justify-center px-6 py-12"
          data-testid="project-hub-backend-unreachable"
        >
          <p className="w-full max-w-md text-center text-sm text-destructive">
            {BACKEND_UNREACHABLE_MESSAGE}
          </p>
        </div>
      )}

      {showEmptyState && !isBackendUnreachable && (() => {
        const showWelcome =
          typeof window !== "undefined" &&
          localStorage.getItem(HAS_HAD_VIDEOS_KEY) !== "true";
        const isNewUser = showWelcome;
        return (
          <div className="flex min-h-[calc(100vh-6rem)] flex-1 flex-col items-center justify-center">
            {showWelcome && (
              <p className="mb-12 max-w-xl text-center text-xl font-medium text-foreground">
                {isNewUser ? (
                  <>
                    <span className={isNewUser ? "empty-state-reveal-welcome" : undefined}>
                      Hello{" "}
                      <span className="noto-color-emoji" aria-hidden>👋</span>
                    </span>
                    <span className={cn(isNewUser && "empty-state-reveal-welcome-rest")}>
                      {EMPTY_WELCOME_REST}
                    </span>
                  </>
                ) : (
                  EMPTY_WELCOME_LEAD + EMPTY_WELCOME_REST
                )}
              </p>
            )}
            <div
              ref={emptyStateZoneRef}
              role="button"
              tabIndex={0}
              className={cn(
                "flex w-full max-w-2xl cursor-pointer flex-col items-center gap-6 rounded-lg border-2 border-dashed px-6 py-12 text-center transition",
                isNewUser && "empty-state-reveal-upload",
                isDragging
                  ? "border-primary bg-accent/10"
                  : "border-border bg-background/95 hover:border-primary/60"
              )}
              onClick={() => {
                if (!isCreating && !isBusyOperation) openFileDialog();
              }}
              onKeyDown={(e) => {
                if ((e.key === "Enter" || e.key === " ") && !isCreating && !isBusyOperation) {
                  e.preventDefault();
                  openFileDialog();
                }
              }}
              onDragEnter={enableRootDrop ? handleDragEnter : undefined}
              onDragOver={enableRootDrop ? handleDragOver : undefined}
              onDragLeave={enableRootDrop ? handleDragLeave : undefined}
              onDrop={enableRootDrop ? handleDrop : undefined}
              data-testid="empty-state-drop-zone"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-current text-muted-foreground">
                <Upload className="h-6 w-6" aria-hidden />
              </div>
              <div className="space-y-1">
                <p className="text-lg font-semibold text-foreground">{EMPTY_MAIN}</p>
                <p className="text-sm text-muted-foreground">{EMPTY_SUPPORTED_FORMATS}</p>
              </div>
            </div>
          </div>
        );
      })()}

      {!isLoading && visibleProjects.length > 0 && (viewMode === "cards" ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visibleProjects.map((project) => {
            const thumbnailSrc = resolveThumbnailSrc(project.thumbnail_path, isTauriEnv);
            const durationLabel = formatDuration(project.duration_seconds);
            const isBusy =
              busyProjectId === project.project_id || deletingProjectId === project.project_id;
            const cardDisabled = isBusyOperation;
            const persistedJob = getPersistedRunningJob(project.project_id);
            const projectForCard = withPersistedActiveTask(project, persistedJob);
            const statusLabel = resolveStatusLabel(projectForCard);
            const projectTitle = resolveProjectTitle(project);
            const effectiveActiveTask = projectForCard.active_task;
            const activeTaskPct =
              typeof effectiveActiveTask?.pct === "number"
                ? Math.max(0, Math.min(100, effectiveActiveTask.pct))
                : 0;
            const taskNotice = project.task_notice;
            const shouldShowTaskNotice =
              !!taskNotice &&
              typeof taskNotice.notice_id === "string" &&
              taskNotice.status !== "cancelled" &&
              !dismissedNoticeIds.has(taskNotice.notice_id);
            const isMissingFile =
              project.missing_video ||
              project.status === "missing_file" ||
              project.status === "needs_video";
            return (
              <div
                key={project.project_id}
                role="button"
                tabIndex={cardDisabled ? -1 : 0}
                onClick={(e) => handleCardClick(e, project)}
                onAuxClick={(e) => handleCardAuxClick(e, project)}
                onKeyDown={(event) => {
                  if (cardDisabled) {
                    return;
                  }
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openProjectTab(project, false);
                  }
                }}
                aria-disabled={cardDisabled}
                aria-busy={isBusy}
                data-testid={`project-card-${project.project_id}`}
                className={cn(
                  "rounded-lg border border-border bg-card p-3 text-left shadow-sm transition-colors duration-200",
                  cardDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-primary/60",
                  isBusy ? "ring-1 ring-primary/40" : ""
                )}
              >
                <div
                  className="relative w-full overflow-hidden rounded-lg border border-border bg-muted"
                  style={{ aspectRatio: "16 / 9" }}
                >
                  {thumbnailSrc ? (
                    <img
                      src={thumbnailSrc}
                      alt={project.title}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
                      Preview not available
                    </div>
                  )}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="absolute right-2 top-2 h-7 w-7 bg-background/80 text-muted-foreground hover:text-destructive"
                        onClick={(event) => {
                          event.stopPropagation();
                          if (cardDisabled) {
                            return;
                          }
                          setDeleteConfirmProject(project);
                        }}
                        onKeyDown={(event) => {
                          event.stopPropagation();
                        }}
                        disabled={cardDisabled}
                        aria-label={`Remove ${resolveProjectTitle(project)} from Cue`}
                        data-testid={`project-card-delete-${project.project_id}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" collisionPadding={8}>{REMOVE_FROM_CUE_LABEL}</TooltipContent>
                  </Tooltip>
                  {effectiveActiveTask && effectiveActiveTask.status !== "queued" && (
                    <div
                      className="absolute bottom-0 left-0 right-0 bg-black/70 px-2 py-1.5"
                      data-testid={`project-card-progress-overlay-${project.project_id}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-white">
                          {Math.round(activeTaskPct)}%
                        </span>
                      </div>
                      <Progress value={activeTaskPct} className="h-1 mt-1 bg-white/20" />
                    </div>
                  )}
                </div>
                <div className="mt-3 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <p className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                          {projectTitle}
                        </p>
                      </TooltipTrigger>
                      <TooltipContent side="top" collisionPadding={8}>
                        {projectTitle}
                      </TooltipContent>
                    </Tooltip>
                    <Badge
                      variant="outline"
                      className={cn("shrink-0", resolveStatusBadgeClassName(projectForCard))}
                    >
                      {statusLabel}
                    </Badge>
                  </div>
                  {durationLabel && (
                    <p className="text-xs text-muted-foreground">{durationLabel}</p>
                  )}
                  {shouldShowTaskNotice && taskNotice && !isMissingFile && (
                    <div
                      className="mt-2 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive"
                      data-testid={`project-card-task-notice-${project.project_id}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span>{taskNotice.message}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-5 w-5 shrink-0 text-destructive hover:text-destructive"
                          aria-label="Dismiss task notice"
                          onClick={(event) => {
                            event.stopPropagation();
                            dismissTaskNotice(taskNotice.notice_id);
                          }}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-muted/50 dark:bg-muted/30">
          <Table className="table-fixed w-full">
            <TableHeader>
              <TableRow>
                <TableHead scope="col" className="min-w-0 px-2" style={{ width: PROJECT_LIST_DATA_COLUMN_WIDTH }}>Video</TableHead>
                <TableHead scope="col" className="min-w-0 pl-2 pr-6" style={{ width: PROJECT_LIST_DATA_COLUMN_WIDTH }}>Duration</TableHead>
                <TableHead scope="col" className="min-w-0 pl-6 pr-2" style={{ width: PROJECT_LIST_DATA_COLUMN_WIDTH }}>Status</TableHead>
                <TableHead scope="col" className="min-w-0 px-2" style={{ width: PROJECT_LIST_DATA_COLUMN_WIDTH }}>Progress</TableHead>
                <TableHead
                  scope="col"
                  className="shrink-0 px-2"
                  style={{ width: PROJECT_LIST_ACTIONS_COLUMN_WIDTH }}
                >
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleProjects.map((project) => {
                const thumbnailSrc = resolveThumbnailSrc(project.thumbnail_path, isTauriEnv);
                const durationLabel = formatDuration(project.duration_seconds);
                const isBusy =
                  busyProjectId === project.project_id || deletingProjectId === project.project_id;
                const cardDisabled = isBusyOperation;
                const persistedJobList = getPersistedRunningJob(project.project_id);
                const projectForList = withPersistedActiveTask(project, persistedJobList);
                const statusLabel = resolveStatusLabel(projectForList);
                const projectTitle = resolveProjectTitle(project);
                const effectiveActiveTaskList = projectForList.active_task;
                const activeTaskPct =
                  typeof effectiveActiveTaskList?.pct === "number"
                    ? Math.max(0, Math.min(100, effectiveActiveTaskList.pct))
                    : 0;
                const activeTaskHeading = resolveTaskHeading(projectForList);
                const hideProgressLabelList =
                  effectiveActiveTaskList?.kind === "create_subtitles" ||
                  effectiveActiveTaskList?.kind === "create_video_with_subtitles";
                const taskNotice = project.task_notice;
                const shouldShowTaskNotice =
                  !!taskNotice &&
                  typeof taskNotice.notice_id === "string" &&
                  taskNotice.status !== "cancelled" &&
                  !dismissedNoticeIds.has(taskNotice.notice_id);
                const isMissingFileList =
                  project.missing_video ||
                  project.status === "missing_file" ||
                  project.status === "needs_video";
                return (
                  <TableRow
                    key={project.project_id}
                    role="button"
                    tabIndex={cardDisabled ? -1 : 0}
                    onClick={(e) => handleCardClick(e, project)}
                    onAuxClick={(e) => handleCardAuxClick(e, project)}
                    onKeyDown={(event) => {
                      if (cardDisabled) return;
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openProjectTab(project, false);
                      }
                    }}
                    aria-disabled={cardDisabled}
                    aria-busy={isBusy}
                    data-testid={`project-list-row-${project.project_id}`}
                    className={cn(
                      cardDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
                      isBusy ? "ring-1 ring-primary/40" : ""
                    )}
                  >
                    <TableCell className="min-w-0 overflow-hidden px-2">
                        <div className="flex min-w-0 items-center gap-2">
                        <div
                          className="relative h-9 w-14 shrink-0 overflow-hidden rounded border border-border bg-muted"
                          style={{ aspectRatio: "16 / 9" }}
                        >
                          {thumbnailSrc ? (
                            <img
                              src={thumbnailSrc}
                              alt={project.title || ""}
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                              —
                            </div>
                          )}
                        </div>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <p className="min-w-0 truncate text-sm font-medium text-foreground">
                              {projectTitle}
                            </p>
                          </TooltipTrigger>
                          <TooltipContent side="top" collisionPadding={8}>
                            {projectTitle}
                          </TooltipContent>
                        </Tooltip>
                      </div>
                    </TableCell>
                    <TableCell className="min-w-0 pl-2 pr-6 tabular-nums text-muted-foreground">
                      {durationLabel || "—"}
                    </TableCell>
                    <TableCell className="min-w-0 overflow-hidden pl-6 pr-2">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Badge
                            variant="outline"
                            className={cn(
                              "max-w-full truncate",
                              resolveStatusBadgeClassName(projectForList)
                            )}
                          >
                            <span className="truncate">{statusLabel}</span>
                          </Badge>
                        </TooltipTrigger>
                        <TooltipContent side="top" collisionPadding={8}>
                          {statusLabel}
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>
                    <TableCell className="min-w-0 overflow-hidden px-2">
                      {effectiveActiveTaskList ? (
                        <div className="space-y-1">
                          {effectiveActiveTaskList.status !== "queued" && !hideProgressLabelList && (
                            <p className="truncate text-xs font-medium text-foreground">
                              {activeTaskHeading}
                            </p>
                          )}
                          {effectiveActiveTaskList && effectiveActiveTaskList.status !== "queued" && (
                            <div className="flex items-center gap-2">
                              <Progress value={activeTaskPct} className="h-1.5 flex-1" />
                              <span className="text-xs text-muted-foreground">
                                {Math.round(activeTaskPct)}%
                              </span>
                            </div>
                          )}
                        </div>
                      ) : shouldShowTaskNotice && taskNotice && !isMissingFileList ? (
                        <div className="flex items-center gap-2">
                          <span className="truncate text-xs text-destructive">
                            {taskNotice.message}
                          </span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 shrink-0 text-destructive hover:text-destructive"
                            aria-label="Dismiss task notice"
                            onClick={(event) => {
                              event.stopPropagation();
                              dismissTaskNotice(taskNotice.notice_id);
                            }}
                          >
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ) : null}
                    </TableCell>
                    <TableCell
                      className="shrink-0 px-2"
                      style={{ width: PROJECT_LIST_ACTIONS_COLUMN_WIDTH }}
                    >
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground hover:text-destructive"
                            onClick={(event) => {
                              event.stopPropagation();
                              if (!cardDisabled) setDeleteConfirmProject(project);
                            }}
                            onKeyDown={(event) => event.stopPropagation()}
                            disabled={cardDisabled}
                            aria-label={`Remove ${resolveProjectTitle(project)} from Cue`}
                            data-testid={`project-list-row-delete-${project.project_id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top" collisionPadding={8}>{REMOVE_FROM_CUE_LABEL}</TooltipContent>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      ))}

      <Dialog
        open={Boolean(deleteConfirmProject)}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteConfirmProject(null);
          }
        }}
      >
        <DialogContent className="z-110" overlayClassName="!z-110">
          <DialogHeader>
            <DialogTitle>{REMOVE_FROM_CUE_LABEL}?</DialogTitle>
            <DialogDescription>
              This removes the video from Cue only. Your original and exported files
              stay on your computer.
            </DialogDescription>
          </DialogHeader>
          {deleteConfirmProject ? (
            <p className="text-sm text-muted-foreground">
              Video: <span className="font-medium text-foreground">{resolveProjectTitle(deleteConfirmProject)}</span>
            </p>
          ) : null}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="tertiary" type="button" disabled={isDeleting}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                void confirmDeleteProject();
              }}
              disabled={isBusyOperation}
              data-testid="confirm-delete-project"
            >
              {isDeleting ? "Removing..." : REMOVE_FROM_CUE_LABEL}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(relinkPromptProject)}
        onOpenChange={(open) => {
          if (!open) {
            setRelinkPromptProject(null);
          }
        }}
      >
        <DialogContent className="z-110" overlayClassName="!z-110">
          <DialogHeader>
            <DialogTitle>Video file not found</DialogTitle>
            <DialogDescription>
              We cannot find the original video file. It may have been moved or renamed. Please
              select it again to continue this project.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="tertiary" type="button">
                Cancel
              </Button>
            </DialogClose>
            <Button
              type="button"
              onClick={() => {
                if (relinkPromptProject) {
                  void beginRelinkSelection(relinkPromptProject);
                }
              }}
              disabled={isBusyOperation}
            >
              Select file
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(relinkWarning)}
        onOpenChange={(open) => {
          if (!open) {
            setRelinkWarning(null);
          }
        }}
      >
        <DialogContent className="z-110" overlayClassName="!z-110">
          <DialogHeader>
            <DialogTitle>This file looks different</DialogTitle>
            <DialogDescription>
              Captions and timing may be wrong if you use a different video.
            </DialogDescription>
          </DialogHeader>
          {relinkWarning?.reasons?.length ? (
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {relinkWarning.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="tertiary" type="button">
                Cancel
              </Button>
            </DialogClose>
            <Button type="button" variant="destructive" onClick={confirmRelinkWarning}>
              Use this file anyway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </div>
    </TooltipProvider>
  );
};

export default ProjectHub;
