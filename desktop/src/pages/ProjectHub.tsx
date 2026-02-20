import * as React from "react";
import { LayoutGrid, List, Trash2, Upload, X } from "lucide-react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { useLocation, useNavigate } from "react-router-dom";

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
import { cn } from "@/lib/utils";
import {
  createProject,
  deleteProject,
  fetchProjects,
  ProjectSummary,
  relinkProject
} from "@/projectsClient";
import { useWorkbenchTabs } from "@/workbenchTabs";
import { waitForBackendHealthy } from "@/backendHealth";

type FileWithPath = File & { path?: string };

type BannerTone = "info" | "error";

type Banner = {
  type: BannerTone;
  message: string;
};

type RelinkWarning = {
  project: ProjectSummary;
  path: string;
  reasons: string[];
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
const MAX_DURATION_DIFF_SECONDS = 3;
const HAS_HAD_VIDEOS_KEY = "cue_has_had_videos";
const PROJECT_HUB_VIEW_KEY = "cue_project_hub_view";
const ADD_VIDEO_BUTTON = "Add video";

type ViewMode = "cards" | "list";

const isValidViewMode = (v: string): v is ViewMode =>
  v === "cards" || v === "list";
const EMPTY_WELCOME_LEAD = "Welcome!";
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
    const src = useTauri ? convertFileSrc(path) : path;

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
  return STATUS_LABELS[project.status] ?? "Not started";
};

const resolveStatusBadgeClassName = (project: ProjectSummary): string => {
  if (project.missing_video) {
    return "border-transparent bg-red-500/15 text-red-700 dark:bg-red-400/20 dark:text-red-300";
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
  if (!path) {
    return "";
  }
  return useTauri ? convertFileSrc(path) : path;
};

const resolveTaskHeading = (project: ProjectSummary) => {
  const heading = project.active_task?.heading;
  if (typeof heading === "string" && heading.trim()) {
    return heading;
  }
  if (project.active_task?.kind === "create_video_with_subtitles") {
    return "Exporting video";
  }
  return "Creating subtitles";
};

const resolveTaskDetail = (project: ProjectSummary) => {
  const checklist = Array.isArray(project.active_task?.checklist) ? project.active_task.checklist : [];
  const activeRow =
    checklist.find((row) => row.state === "active") ??
    checklist.find((row) => row.id === project.active_task?.step_id);
  if (activeRow?.detail && activeRow.detail.trim()) {
    return activeRow.detail.trim();
  }
  const message = project.active_task?.message;
  return typeof message === "string" ? message.trim() : "";
};

const ProjectHub = () => {
  const location = useLocation();
  const incomingState = location.state as ProjectHubLocationState;
  const navigate = useNavigate();
  const { openSettings } = useSettings();
  const { pushToast } = useToast();
  const { closeTab, openOrActivateTab } = useWorkbenchTabs();
  const [projects, setProjects] = React.useState<ProjectSummary[]>([]);
  const [optimisticallyHiddenProjectIds, setOptimisticallyHiddenProjectIds] =
    React.useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = React.useState(true);
  const [isBackendStarting, setIsBackendStarting] = React.useState(true);
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

  const loadProjects = React.useCallback(async () => {
    setIsLoading(true);
    setIsBackendStarting(true);
    try {
      await waitForBackendHealthy();
      setIsBackendStarting(false);
      const data = await fetchProjects();
      setProjects(data);
      if (data.length > 0) {
        try {
          localStorage.setItem(HAS_HAD_VIDEOS_KEY, "true");
        } catch {
          /* ignore */
        }
      }
    } catch (err) {
      setBanner({
        type: "error",
        message:
          err instanceof Error && err.message === "backend_start_timeout"
            ? "Cue is still starting in the background. Please wait a moment and try again."
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
    const pollDelay = projects.some((project) => Boolean(project.active_task))
      ? ACTIVE_TASK_POLL_MS
      : IDLE_TASK_POLL_MS;
    const timer = window.setTimeout(async () => {
      try {
        const data = await fetchProjects();
        if (!cancelled) {
          setProjects(data);
          if (data.length > 0) {
            try {
              localStorage.setItem(HAS_HAD_VIDEOS_KEY, "true");
            } catch {
              /* ignore */
            }
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
      setBanner(null);
      setIsCreating(true);
      try {
        const createdProject = await createProject(videoPath);
        await loadProjects();
        openOrActivateTab({
          projectId: createdProject.project_id,
          title: resolveProjectTitle(createdProject)
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

  const handleFileSelected = (file: File) => {
    const resolvedPath = resolveFilePath(file);
    if (!resolvedPath) {
      showBanner("error", "Could not read this file path. Please try a different file.");
      return;
    }
    handleCreateProject(resolvedPath);
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleFileSelected(file);
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
      handleFileSelected(file);
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
    async (project: ProjectSummary, videoPath: string) => {
      setBanner(null);
      setBusyProjectId(project.project_id);
      try {
        await relinkProject(project.project_id, videoPath);
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
      selectedPath: string,
      selectedFileName: string,
      selectedDuration: number | null
    ) => {
      if (!isSupportedVideo(selectedFileName)) {
        showBanner("error", "Unsupported file type. Choose an MP4, MKV, MOV, or M4V file.");
        return;
      }
      const warnings = buildRelinkWarnings(project, selectedFileName, selectedDuration);
      if (warnings.length > 0) {
        setRelinkWarning({ project, path: selectedPath, reasons: warnings });
        return;
      }
      await performRelink(project, selectedPath);
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
            const selectedFileName = getFileName(selected);
            await handleRelinkSelection(project, selected, selectedFileName, duration);
          }
        } catch {
          showBanner("error", "Could not open the file picker. Please try again.");
        }
        return;
      }
      setPendingRelinkProject(project);
      relinkInputRef.current?.click();
    },
    [handleRelinkSelection, isBusyOperation, isTauriEnv, showBanner]
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
    const resolvedPath = resolveFilePath(file);
    if (!resolvedPath) {
      showBanner("error", "Could not read this file path. Please try a different file.");
      return;
    }
    const duration = await getVideoDurationFromFile(file);
    await handleRelinkSelection(project, resolvedPath, file.name, duration);
  };

  const handleCardClick = (project: ProjectSummary) => {
    if (isBusyOperation) {
      return;
    }
    if (project.missing_video || project.status === "missing_file") {
      setRelinkPromptProject(project);
      return;
    }
    openOrActivateTab({ projectId: project.project_id, title: resolveProjectTitle(project) });
    navigate(`/workbench/${encodeURIComponent(project.project_id)}`);
  };

  const confirmRelinkWarning = async () => {
    if (!relinkWarning) {
      return;
    }
    const { project, path } = relinkWarning;
    setRelinkWarning(null);
    await performRelink(project, path);
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
      const result = await deleteProject(project.project_id);
      setProjects((prev) => prev.filter((entry) => entry.project_id !== project.project_id));
      closeTab(project.project_id);
      const cancelledCount = Array.isArray(result.cancelled_job_ids)
        ? result.cancelled_job_ids.length
        : 0;
      const cancelledMessage =
        cancelledCount > 0
          ? ` Running job cancelled first${cancelledCount > 1 ? " (multiple jobs)." : "."}`
          : "";
      const displayName =
        truncateForToast(resolveProjectTitle(project).trim()) || "The video";
      const message = `${displayName} was removed.${cancelledMessage.trim() ? ` ${cancelledMessage.trim()}` : ""}`;
      // D4: delete success must be toast, not inline banner (CUE_UX_UI_SPEC).
      pushToast("Video deleted", message);
    } catch (err) {
      showBanner("error", err instanceof Error ? err.message : "Failed to delete video.");
    } finally {
      setDeletingProjectId(null);
    }
  }, [closeTab, deleteConfirmProject, isBusyOperation, pushToast, showBanner]);

  const visibleProjects = React.useMemo(
    () =>
      projects.filter((project) => !optimisticallyHiddenProjectIds.has(project.project_id)),
    [optimisticallyHiddenProjectIds, projects]
  );
  const showEmptyState = !isLoading && visibleProjects.length === 0;
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
    <div
      data-testid="project-hub"
      className="space-y-6 rounded-lg border border-transparent p-1"
      onDragOver={enableRootDrop ? handleRootDragOver : undefined}
      onDrop={enableRootDrop ? handleDrop : undefined}
    >
      {!showEmptyState && (
        <PageHeader
          title={<h1 className="text-2xl font-semibold text-foreground">Videos</h1>}
          onOpenSettings={openSettings}
          showSettings={!isTauriEnv}
          right={
            <>
              {visibleProjects.length > 0 && (
                <TooltipProvider delayDuration={300}>
                  <ToggleGroup
                    type="single"
                    variant="outline"
                    value={viewMode}
                    onValueChange={(v) => v && isValidViewMode(v) && setViewMode(v)}
                    className="inline-flex [&_[data-slot=toggle-group-item]]:h-[38px]"
                  >
                    <ToggleGroupItem value="cards" aria-label="Card view" className="relative">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span
                            className="absolute inset-0 rounded-[inherit]"
                            onClick={(e) => (e.target as HTMLElement).closest("button")?.click()}
                          />
                        </TooltipTrigger>
                        <TooltipContent side="bottom" sideOffset={14}>Card view</TooltipContent>
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
                        <TooltipContent side="bottom" sideOffset={14}>List view</TooltipContent>
                      </Tooltip>
                      <List className="relative z-10 h-4 w-4" />
                    </ToggleGroupItem>
                  </ToggleGroup>
                </TooltipProvider>
              )}
              <Button onClick={openFileDialog} disabled={isCreating || isBusyOperation}>
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

      {banner && (
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

      {isLoading && (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          {isBackendStarting ? "Starting the engine..." : "Loading videos..."}
        </div>
      )}

      {showEmptyState && (() => {
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
                      {EMPTY_WELCOME_LEAD}
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
                isDragging ? "border-primary bg-accent/10" : "border-border bg-card hover:border-primary/60"
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
            const statusLabel = resolveStatusLabel(project);
            const isBusy =
              busyProjectId === project.project_id || deletingProjectId === project.project_id;
            const cardDisabled = isBusyOperation;
            const activeTaskPct =
              typeof project.active_task?.pct === "number"
                ? Math.max(0, Math.min(100, project.active_task.pct))
                : 0;
            const activeTaskDetail = resolveTaskDetail(project);
            const activeTaskHeading = resolveTaskHeading(project);
            const taskNotice = project.task_notice;
            const shouldShowTaskNotice =
              !!taskNotice &&
              typeof taskNotice.notice_id === "string" &&
              taskNotice.status !== "cancelled" &&
              !dismissedNoticeIds.has(taskNotice.notice_id);
            return (
              <div
                key={project.project_id}
                role="button"
                tabIndex={cardDisabled ? -1 : 0}
                onClick={() => handleCardClick(project)}
                onKeyDown={(event) => {
                  if (cardDisabled) {
                    return;
                  }
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    handleCardClick(project);
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
                    aria-label={`Delete ${resolveProjectTitle(project)}`}
                    data-testid={`project-card-delete-${project.project_id}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                <div className="mt-3 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                      {project.title || "Untitled video"}
                    </p>
                    <Badge variant="outline" className={cn("shrink-0", resolveStatusBadgeClassName(project))}>
                      {statusLabel}
                    </Badge>
                  </div>
                  {durationLabel && (
                    <p className="text-xs text-muted-foreground">{durationLabel}</p>
                  )}
                  {project.active_task && (
                    <div
                      className="mt-2 space-y-1 rounded-md border border-border bg-muted/40 p-2"
                      data-testid={`project-card-active-task-${project.project_id}`}
                    >
                      <p className="text-xs font-medium text-foreground">{activeTaskHeading}</p>
                      {activeTaskDetail && (
                        <p className="truncate text-xs text-muted-foreground">
                          {activeTaskDetail}
                        </p>
                      )}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>{Math.round(activeTaskPct)}%</span>
                        </div>
                        <Progress value={activeTaskPct} />
                      </div>
                    </div>
                  )}
                  {shouldShowTaskNotice && taskNotice && (
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
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Video</TableHead>
                <TableHead scope="col" className="min-w-[5rem] pr-24 text-right">Duration</TableHead>
                <TableHead scope="col">Status</TableHead>
                <TableHead scope="col">Progress</TableHead>
                <TableHead scope="col" className="w-[60px]">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleProjects.map((project) => {
                const thumbnailSrc = resolveThumbnailSrc(project.thumbnail_path, isTauriEnv);
                const durationLabel = formatDuration(project.duration_seconds);
                const statusLabel = resolveStatusLabel(project);
                const isBusy =
                  busyProjectId === project.project_id || deletingProjectId === project.project_id;
                const cardDisabled = isBusyOperation;
                const activeTaskPct =
                  typeof project.active_task?.pct === "number"
                    ? Math.max(0, Math.min(100, project.active_task.pct))
                    : 0;
                const activeTaskHeading = resolveTaskHeading(project);
                const taskNotice = project.task_notice;
                const shouldShowTaskNotice =
                  !!taskNotice &&
                  typeof taskNotice.notice_id === "string" &&
                  taskNotice.status !== "cancelled" &&
                  !dismissedNoticeIds.has(taskNotice.notice_id);
                return (
                  <TableRow
                    key={project.project_id}
                    role="button"
                    tabIndex={cardDisabled ? -1 : 0}
                    onClick={() => handleCardClick(project)}
                    onKeyDown={(event) => {
                      if (cardDisabled) return;
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        handleCardClick(project);
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
                    <TableCell className="whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div
                          className="relative h-9 w-16 shrink-0 overflow-hidden rounded border border-border bg-muted"
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
                        <p className="min-w-0 truncate text-sm font-medium text-foreground">
                          {project.title || "Untitled video"}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell className="min-w-[5rem] pr-24 text-right tabular-nums text-muted-foreground">
                      {durationLabel || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={resolveStatusBadgeClassName(project)}>
                      {statusLabel}
                    </Badge>
                    </TableCell>
                    <TableCell className="min-w-[140px]">
                      {project.active_task ? (
                        <div className="space-y-1">
                          <p className="truncate text-xs font-medium text-foreground">
                            {activeTaskHeading}
                          </p>
                          <div className="flex items-center gap-2">
                            <Progress value={activeTaskPct} className="h-1.5 flex-1" />
                            <span className="text-xs text-muted-foreground">
                              {Math.round(activeTaskPct)}%
                            </span>
                          </div>
                        </div>
                      ) : shouldShowTaskNotice && taskNotice ? (
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
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="w-[60px]">
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
                        aria-label={`Delete ${resolveProjectTitle(project)}`}
                        data-testid={`project-list-row-delete-${project.project_id}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete video?</DialogTitle>
            <DialogDescription>
              This removes the video from Cue. Your original video file stays on your
              computer.
            </DialogDescription>
          </DialogHeader>
          {deleteConfirmProject ? (
            <p className="text-sm text-muted-foreground">
              Video: <span className="font-medium text-foreground">{resolveProjectTitle(deleteConfirmProject)}</span>
            </p>
          ) : null}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="ghost" type="button" disabled={isDeleting}>
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
              {isDeleting ? "Deleting..." : "Delete video"}
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Video file not found</DialogTitle>
            <DialogDescription>
              We cannot find the original video file. It may have been moved or renamed. Please
              select it again to continue this project.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="ghost" type="button">
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
        <DialogContent>
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
              <Button variant="ghost" type="button">
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
  );
};

export default ProjectHub;
