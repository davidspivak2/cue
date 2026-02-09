import * as React from "react";
import { ArrowLeft } from "lucide-react";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { fetchProject, ProjectManifest } from "@/projectsClient";
import { useWindowWidth } from "@/hooks/useWindowWidth";
import { useWorkbenchTabs } from "@/workbenchTabs";

const STATUS_LABELS: Record<string, string> = {
  needs_video: "Needs video",
  needs_subtitles: "Needs subtitles",
  ready: "Ready",
  exporting: "Exporting",
  done: "Done",
  missing_file: "Missing file"
};

const getFileName = (value?: string | null) => {
  if (!value) {
    return "Untitled project";
  }
  const parts = value.split(/[/\\]/);
  return parts[parts.length - 1] ?? value;
};

const resolveTitle = (project: ProjectManifest | null) => {
  const filename = project?.video?.filename ?? project?.video?.path ?? "";
  return filename ? getFileName(filename) : "Untitled project";
};

const resolveStatusLabel = (status?: string | null) => {
  if (!status) {
    return "Loading";
  }
  return STATUS_LABELS[status] ?? "Needs subtitles";
};

const Workbench = () => {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { tabs, ensureTab, updateTabMeta } = useWorkbenchTabs();
  const width = useWindowWidth();
  const isNarrow = width < 1100;
  const isTauriEnv = isTauri();
  const [project, setProject] = React.useState<ProjectManifest | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [leftPanelOpen, setLeftPanelOpen] = React.useState(false);
  const [rightOverlayOpen, setRightOverlayOpen] = React.useState(false);
  const showSubtitlesOverlay = false;

  React.useEffect(() => {
    let active = true;
    if (!projectId) {
      setError("Missing project id.");
      setIsLoading(false);
      return () => {
        active = false;
      };
    }
    setIsLoading(true);
    fetchProject(projectId)
      .then((data) => {
        if (!active) return;
        setProject(data);
        setError(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load project.");
      })
      .finally(() => {
        if (!active) return;
        setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  React.useEffect(() => {
    if (!projectId) {
      return;
    }
    ensureTab({ projectId, title: "Loading..." });
  }, [ensureTab, projectId]);

  React.useEffect(() => {
    if (!projectId) {
      return;
    }
    setLeftPanelOpen(false);
    setRightOverlayOpen(false);
  }, [projectId]);

  React.useEffect(() => {
    if (!projectId || !project) {
      return;
    }
    updateTabMeta(projectId, { title: resolveTitle(project) });
  }, [project, projectId, updateTabMeta]);

  React.useEffect(() => {
    if (!isNarrow) {
      setRightOverlayOpen(false);
    }
  }, [isNarrow]);

  const title = resolveTitle(project);
  const statusLabel = resolveStatusLabel(project?.status);
  const videoPath = project?.video?.path ?? "";
  const previewSrc = videoPath ? (isTauriEnv ? convertFileSrc(videoPath) : videoPath) : "";
  const hasVideoPreview = Boolean(previewSrc);
  const showLeftToggle = showSubtitlesOverlay && !leftPanelOpen;
  const isOverlayOpen = (showSubtitlesOverlay && leftPanelOpen) || rightOverlayOpen;
  const showScrim = isNarrow && isOverlayOpen;

  const openLeftPanel = () => {
    if (!showSubtitlesOverlay) {
      return;
    }
    if (isNarrow) {
      setRightOverlayOpen(false);
    }
    setLeftPanelOpen(true);
  };

  const closeLeftPanel = () => {
    setLeftPanelOpen(false);
  };

  const openRightOverlay = () => {
    if (!isNarrow) {
      return;
    }
    setLeftPanelOpen(false);
    setRightOverlayOpen(true);
  };

  const closeOverlays = React.useCallback(() => {
    if (showSubtitlesOverlay && leftPanelOpen) {
      setLeftPanelOpen(false);
    }
    if (rightOverlayOpen) {
      setRightOverlayOpen(false);
    }
  }, [leftPanelOpen, rightOverlayOpen, showSubtitlesOverlay]);

  React.useEffect(() => {
    if (!isOverlayOpen) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeOverlays();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeOverlays, isOverlayOpen]);

  const handleSelectTab = (targetId: string) => {
    if (targetId === projectId) {
      return;
    }
    navigate(`/workbench/${encodeURIComponent(targetId)}`);
  };

  return (
    <div data-testid="workbench" className="flex h-[calc(100vh-3rem)] flex-col gap-4">
      <div
        className="flex flex-wrap items-center gap-2 border-b border-border pb-2"
        role="tablist"
        aria-label="Open projects"
        data-testid="workbench-tabs"
      >
        {tabs.length === 0 ? (
          <span className="text-xs text-muted-foreground">No open projects</span>
        ) : (
          tabs.map((tab) => {
            const isActive = tab.projectId === projectId;
            const label = tab.title || "Untitled project";
            return (
              <div
                key={tab.projectId}
                className={cn(
                  "flex items-center rounded-md border px-2 py-1 text-sm",
                  isActive ? "border-primary/60 bg-accent/20" : "border-border bg-card"
                )}
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "max-w-[180px] truncate text-left text-sm",
                    isActive ? "text-foreground" : "text-muted-foreground"
                  )}
                  title={label}
                  data-testid={`workbench-tab-${tab.projectId}`}
                  onClick={() => handleSelectTab(tab.projectId)}
                >
                  {label}
                </button>
              </div>
            );
          })
        )}
      </div>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="gap-2"
          onClick={() => navigate("/")}
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <div className="min-w-0 text-center">
          <h1 className="text-lg font-semibold">Workbench</h1>
          <p className="truncate text-sm text-muted-foreground">{title}</p>
        </div>
        <Badge variant="secondary">{statusLabel}</Badge>
      </header>

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Loading project…
        </div>
      )}

      {!isLoading && error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!isLoading && !error && (
        <>
          {((showSubtitlesOverlay && showLeftToggle) || isNarrow) && (
            <div className="relative z-50 flex flex-wrap items-center gap-2">
              {showSubtitlesOverlay && showLeftToggle && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openLeftPanel}
                  data-testid="workbench-open-left"
                >
                  All subtitles
                </Button>
              )}
              {isNarrow && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openRightOverlay}
                  data-testid="workbench-open-style"
                >
                  Style
                </Button>
              )}
            </div>
          )}

          <div className={cn("flex min-h-0 flex-1 gap-4", isNarrow ? "flex-col" : "flex-row")}>
            <section
              className="flex min-h-[220px] flex-1 items-center justify-center rounded-lg border border-border bg-muted p-4"
              data-testid="workbench-center-panel"
            >
              {hasVideoPreview ? (
                <video
                  className="h-full w-full rounded-md bg-black object-contain"
                  controls
                  src={previewSrc}
                />
              ) : (
                <div className="text-sm text-muted-foreground">Preview not available</div>
              )}
            </section>

            {!isNarrow && (
              <section
                className="flex min-h-0 w-80 shrink-0 flex-col rounded-lg border border-border bg-card"
                data-testid="workbench-right-panel"
              >
                <div className="border-b border-border px-4 py-2">
                  <h2 className="text-sm font-semibold">Style</h2>
                </div>
                <ScrollArea className="min-h-0 flex-1 px-4 py-3">
                  <p className="text-xs text-muted-foreground">
                    Placeholder — style controls will live here.
                  </p>
                </ScrollArea>
              </section>
            )}
          </div>

          {showScrim && (
            <div
              className="fixed inset-0 z-40 bg-black/40"
              onClick={closeOverlays}
              data-testid="workbench-overlay-scrim"
            />
          )}

          {showSubtitlesOverlay && leftPanelOpen && (
            <aside
              className="fixed inset-y-0 left-0 z-50 flex w-[min(90vw,360px)] flex-col border-r border-border bg-card shadow-lg"
              data-testid="workbench-left-drawer"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2">
                <h2 className="text-sm font-semibold">All subtitles</h2>
                <Button variant="ghost" size="sm" onClick={closeLeftPanel}>
                  Close
                </Button>
              </div>
              <ScrollArea className="min-h-0 flex-1 px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  Placeholder — subtitles list will live here.
                </p>
              </ScrollArea>
            </aside>
          )}

          {isNarrow && rightOverlayOpen && (
            <aside
              className="fixed inset-y-0 right-0 z-50 flex w-[min(90vw,320px)] flex-col border-l border-border bg-card shadow-lg"
              data-testid="workbench-right-drawer"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2">
                <h2 className="text-sm font-semibold">Style</h2>
                <Button variant="ghost" size="sm" onClick={() => setRightOverlayOpen(false)}>
                  Close
                </Button>
              </div>
              <ScrollArea className="min-h-0 flex-1 px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  Placeholder — style controls will live here.
                </p>
              </ScrollArea>
            </aside>
          )}
        </>
      )}
    </div>
  );
};

export default Workbench;
