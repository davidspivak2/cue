import * as React from "react";
import { X } from "lucide-react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { useNavigate } from "react-router-dom";

import DropZone from "@/components/DropZone";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { createProject, fetchProjects, ProjectSummary, relinkProject } from "@/projectsClient";
import { useWorkbenchTabs } from "@/workbenchTabs";

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

const STATUS_LABELS: Record<string, string> = {
  ready: "Ready",
  exporting: "Exporting",
  done: "Done",
  missing_file: "Missing file",
  needs_video: "Missing file",
  needs_subtitles: "Needs subtitles"
};

const SUPPORTED_EXTENSIONS = new Set(["mp4", "mkv", "mov", "m4v"]);
const MAX_DURATION_DIFF_SECONDS = 3;

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
  return "Untitled project";
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
  return STATUS_LABELS[project.status] ?? "Needs subtitles";
};

const resolveThumbnailSrc = (path: string | null | undefined, useTauri: boolean) => {
  if (!path) {
    return "";
  }
  return useTauri ? convertFileSrc(path) : path;
};

const ProjectHub = () => {
  const navigate = useNavigate();
  const { openOrActivateTab } = useWorkbenchTabs();
  const [projects, setProjects] = React.useState<ProjectSummary[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [banner, setBanner] = React.useState<Banner | null>(null);
  const [isDragging, setIsDragging] = React.useState(false);
  const [isCreating, setIsCreating] = React.useState(false);
  const [relinkPromptProject, setRelinkPromptProject] = React.useState<ProjectSummary | null>(
    null
  );
  const [relinkWarning, setRelinkWarning] = React.useState<RelinkWarning | null>(null);
  const [pendingRelinkProject, setPendingRelinkProject] = React.useState<ProjectSummary | null>(
    null
  );
  const [busyProjectId, setBusyProjectId] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const relinkInputRef = React.useRef<HTMLInputElement>(null);

  const isTauriEnv = isTauri();
  const isRelinking = busyProjectId !== null;

  const showBanner = React.useCallback((type: BannerTone, message: string) => {
    setBanner({ type, message });
  }, []);

  const loadProjects = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await fetchProjects();
      setProjects(data);
    } catch (err) {
      setBanner({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to load projects."
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreateProject = React.useCallback(
    async (videoPath: string) => {
      if (!videoPath) {
        showBanner("error", "Could not read this file path. Please try a different file.");
        return;
      }
      setBanner(null);
      setIsCreating(true);
      try {
        await createProject(videoPath);
        await loadProjects();
      } catch (err) {
        showBanner("error", err instanceof Error ? err.message : "Failed to create project.");
      } finally {
        setIsCreating(false);
      }
    },
    [loadProjects, showBanner]
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
    if (isCreating || isRelinking) {
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
            extensions: ["mp4", "mkv", "mov", "m4v"]
          }
        ],
        pickerMode: "video"
      });
      if (typeof selected === "string" && selected) {
        await handleCreateProject(selected);
      }
    } catch (dialogError) {
      showBanner("error", "Could not open the file picker. Please try again.");
    }
  }, [handleCreateProject, isCreating, isRelinking, isTauriEnv, showBanner]);

  React.useEffect(() => {
    if (!isTauriEnv) {
      return;
    }
    let unlisten: (() => void) | null = null;
    getCurrentWebview()
      .onDragDropEvent((event) => {
        const payload = event.payload;
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
    if (isCreating || isRelinking) {
      return;
    }
    setIsDragging(true);
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (isCreating || isRelinking) {
      return;
    }
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    if (isCreating || isRelinking) {
      return;
    }
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (isCreating || isRelinking) {
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
      if (isRelinking) {
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
                extensions: ["mp4", "mkv", "mov", "m4v"]
              }
            ],
            pickerMode: "video"
          });
          if (typeof selected === "string" && selected) {
            const duration = await getVideoDurationFromPath(selected, isTauriEnv);
            const selectedFileName = getFileName(selected);
            await handleRelinkSelection(project, selected, selectedFileName, duration);
          }
        } catch (dialogError) {
          showBanner("error", "Could not open the file picker. Please try again.");
        }
        return;
      }
      setPendingRelinkProject(project);
      relinkInputRef.current?.click();
    },
    [handleRelinkSelection, isRelinking, isTauriEnv, showBanner]
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
    if (isRelinking) {
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

  const showEmptyState = !isLoading && projects.length === 0;
  const enableRootDrop = !isTauriEnv && !showEmptyState && !isRelinking;

  return (
    <div
      data-testid="project-hub"
      className={cn(
        "space-y-6 rounded-lg border border-transparent p-1",
        isDragging && !isTauriEnv ? "border-primary/60 bg-accent/10" : ""
      )}
      onDragEnter={enableRootDrop ? handleDragEnter : undefined}
      onDragOver={enableRootDrop ? handleDragOver : undefined}
      onDragLeave={enableRootDrop ? handleDragLeave : undefined}
      onDrop={enableRootDrop ? handleDrop : undefined}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Project Hub</h1>
          <p className="text-sm text-muted-foreground">
            Create a new project or open an existing one.
          </p>
        </div>
        <Button onClick={openFileDialog} disabled={isCreating || isRelinking}>
          New project
        </Button>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={handleInputChange}
        disabled={isCreating || isRelinking}
        data-testid="new-project-input"
      />

      <input
        ref={relinkInputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={handleRelinkInputChange}
        disabled={isRelinking}
        data-testid="relink-input"
      />

      {banner && (
        <div
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
          Loading projects…
        </div>
      )}

      {showEmptyState &&
        (isTauriEnv ? (
          <div
            className={cn(
              "flex flex-col items-center gap-3 rounded-lg border-2 border-dashed px-6 py-12 text-center",
              isDragging ? "border-primary bg-accent/10" : "border-border bg-card"
            )}
          >
            <p className="text-lg font-semibold text-foreground">No projects yet</p>
            <p className="text-sm text-muted-foreground">
              Drop a video anywhere on this screen or use “New project”.
            </p>
            <Button
              variant="secondary"
              onClick={openFileDialog}
              disabled={isCreating || isRelinking}
            >
              New project
            </Button>
          </div>
        ) : (
          <DropZone
            onFileSelected={handleFileSelected}
            disabled={isCreating || isRelinking}
            className="rounded-lg"
          />
        ))}

      {!isLoading && projects.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {projects.map((project) => {
            const thumbnailSrc = resolveThumbnailSrc(project.thumbnail_path, isTauriEnv);
            const durationLabel = formatDuration(project.duration_seconds);
            const statusLabel = resolveStatusLabel(project);
            const isBusy = busyProjectId === project.project_id;
            return (
              <button
                key={project.project_id}
                type="button"
                onClick={() => handleCardClick(project)}
                disabled={isRelinking}
                aria-busy={isBusy}
                className={cn(
                  "rounded-lg border bg-card p-3 text-left transition",
                  isRelinking ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-primary/60",
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
                  <Badge variant="secondary" className="absolute left-2 top-2">
                    {statusLabel}
                  </Badge>
                </div>
                <div className="mt-3 space-y-1">
                  <p className="truncate text-sm font-medium text-foreground">
                    {project.title || "Untitled project"}
                  </p>
                  {durationLabel && (
                    <p className="text-xs text-muted-foreground">{durationLabel}</p>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}

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
              disabled={isRelinking}
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
