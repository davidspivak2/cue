import * as React from "react";
import { createPortal } from "react-dom";
import { Suspense } from "react";
import { X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import TabHost from "@/pages/TabHost";
import { isTauri } from "@tauri-apps/api/core";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";

import TitleBar, { TITLE_BAR_HEIGHT, TITLE_BAR_HEIGHT_PX } from "@/components/TitleBar";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useAppSplash } from "@/contexts/AppSplashContext";
import { waitForBackendHealthy } from "@/backendHealth";
import { CalibrationProvider } from "@/contexts/CalibrationContext";
import { DeviceInfoProvider } from "@/contexts/DeviceInfoContext";
import { RunningJobsProvider } from "@/contexts/RunningJobsContext";
import { SettingsProvider } from "@/contexts/SettingsContext";
import { ToastProvider } from "@/contexts/ToastContext";
import { ExitConfirmHandler } from "@/components/ExitConfirmHandler";
import EngineSkeletonLoader from "@/components/EngineSkeletonLoader";

const Settings = React.lazy(() => import("@/pages/Settings"));
import { fetchProjects } from "@/projectsClient";
import { WorkbenchTabsProvider } from "@/workbenchTabs";

const ACTIVE_TASK_POLL_MS = 2500;
const IDLE_TASK_POLL_MS = 10000;

type ToastAction = {
  label: string;
  onClick: () => void;
};

type ToastItem = {
  id: string;
  title: string;
  message: string;
  actions?: ToastAction[];
};

const getExportCompleteKey = (projectId: string, outputPath: string, exportedAt: string) =>
  `${projectId}:${outputPath}:${exportedAt}`;

const AppLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { setShowSplash } = useAppSplash();
  const hasLaunchedRef = React.useRef(false);

  React.useEffect(() => {
    if (typeof document !== "undefined") document.body.removeAttribute("data-tauri-drag-region");
  }, []);

  React.useEffect(() => {
    if (!isTauri()) {
      setShowSplash(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        await waitForBackendHealthy({ timeoutMs: 120_000, intervalMs: 400 });
      } catch {
        /* splash still dismissed so ProjectHub / errors can show */
      }
      if (!cancelled) {
        setShowSplash(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setShowSplash]);
  const seenNoticeIdsRef = React.useRef<Set<string>>(new Set());
  const seenExportCompleteRef = React.useRef<Set<string>>(new Set());
  const exportToastBaselineReadyRef = React.useRef(false);
  const locationRef = React.useRef(location);
  locationRef.current = location;
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [settingsScrolled, setSettingsScrolled] = React.useState(false);
  const [diagnosticsRevealed, setDiagnosticsRevealed] = React.useState(false);
  const settingsScrollRef = React.useRef<HTMLDivElement>(null);
  const settingsTapCountRef = React.useRef(0);
  const openSettings = React.useCallback(() => setSettingsOpen(true), []);
  const closeSettings = React.useCallback(() => setSettingsOpen(false), []);

  React.useEffect(() => {
    if (!settingsOpen) {
      setSettingsScrolled(false);
      return;
    }
    let cancelled = false;
    let teardown: (() => void) | null = null;
    const id = window.setTimeout(() => {
      if (cancelled) return;
      const root = settingsScrollRef.current;
      if (!root) return;
      const viewport = root.querySelector("[data-radix-scroll-area-viewport]");
      if (!viewport || cancelled) return;
      const handler = () =>
        setSettingsScrolled((viewport as HTMLElement).scrollTop > 0);
      handler();
      viewport.addEventListener("scroll", handler);
      teardown = () => {
        viewport.removeEventListener("scroll", handler);
        setSettingsScrolled(false);
      };
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
      teardown?.();
    };
  }, [settingsOpen]);

  const removeToast = React.useCallback((toastId: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== toastId));
  }, []);

  const pushToast = React.useCallback(
    (
      title: string,
      message: string,
      options?: { actions?: ToastAction[] }
    ) => {
      const toastId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setToasts((prev) =>
        [...prev, { id: toastId, title, message, actions: options?.actions }].slice(-4)
      );
      window.setTimeout(() => {
        removeToast(toastId);
      }, 8000);
    },
    [removeToast]
  );

  const markExportCompleteSeen = React.useCallback(
    (projectId: string, outputPath: string, exportedAt: string) => {
      seenExportCompleteRef.current.add(getExportCompleteKey(projectId, outputPath, exportedAt));
    },
    []
  );

  const haveExportCompleteBeenSeen = React.useCallback(
    (projectId: string, outputPath: string, exportedAt: string) => {
      return seenExportCompleteRef.current.has(
        getExportCompleteKey(projectId, outputPath, exportedAt)
      );
    },
    []
  );

  React.useEffect(() => {
    if (hasLaunchedRef.current) {
      return;
    }
    hasLaunchedRef.current = true;
    const onWorkbench = /^\/workbench\/[^/]+$/.test(location.pathname);
    if (location.pathname !== "/" && !onWorkbench) {
      navigate("/", { replace: true });
    }
  }, [location.pathname, navigate]);

  React.useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const poll = async () => {
      let nextDelay = IDLE_TASK_POLL_MS;
      try {
        const projects = await fetchProjects();
        nextDelay = projects.some((project) => Boolean(project.active_task))
          ? ACTIVE_TASK_POLL_MS
          : IDLE_TASK_POLL_MS;
        for (const project of projects) {
          const notice = project.task_notice;
          if (!notice || !notice.notice_id || !notice.message) {
            continue;
          }
          if (seenNoticeIdsRef.current.has(notice.notice_id)) {
            continue;
          }
          seenNoticeIdsRef.current.add(notice.notice_id);
          const isSuppressedCancelledNotice = notice.status === "cancelled";
          if (isSuppressedCancelledNotice) {
            continue;
          }
          const pathname = locationRef.current.pathname;
          const workbenchMatch = pathname.match(/^\/workbench\/(.+)$/);
          const currentProjectId = workbenchMatch ? decodeURIComponent(workbenchMatch[1]) : null;
          if (currentProjectId === project.project_id) {
            continue;
          }
          const title = notice.status === "cancelled" ? "Task cancelled" : "Task failed";
          const projectTitle = project.title || "Video";
          pushToast(projectTitle, `${title}: ${notice.message}`);
        }
        for (const project of projects) {
          const outputPath = project.latest_export?.output_video_path;
          if (!outputPath) {
            continue;
          }
          const exportedAt = project.latest_export?.exported_at ?? "";
          const key = getExportCompleteKey(project.project_id, outputPath, exportedAt);
          if (!exportToastBaselineReadyRef.current) {
            seenExportCompleteRef.current.add(key);
            continue;
          }
          if (project.active_task) {
            continue;
          }
          if (seenExportCompleteRef.current.has(key)) {
            continue;
          }
          seenExportCompleteRef.current.add(key);
          const filename =
            outputPath.split(/[/\\]/).filter(Boolean).pop() ?? outputPath;
          const actions: ToastAction[] = [];
          if (isTauri()) {
            actions.push(
              {
                label: "Play",
                onClick: () => {
                  void openPath(outputPath);
                }
              },
              {
                label: "Open folder",
                onClick: () => {
                  void revealItemInDir(outputPath);
                }
              }
            );
          }
          pushToast("Export complete", filename, { actions });
        }
        exportToastBaselineReadyRef.current = true;
      } catch {
        nextDelay = IDLE_TASK_POLL_MS;
      } finally {
        if (!cancelled) {
          timer = setTimeout(poll, nextDelay);
        }
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [pushToast]);

  return (
    <DeviceInfoProvider>
      <CalibrationProvider>
      <RunningJobsProvider>
        <ExitConfirmHandler />
        <WorkbenchTabsProvider>
        <SettingsProvider
          openSettings={openSettings}
          closeSettings={closeSettings}
          settingsOpen={settingsOpen}
          diagnosticsSectionVisible={diagnosticsRevealed}
        >
          <ToastProvider
          pushToast={pushToast}
          markExportCompleteSeen={markExportCompleteSeen}
          haveExportCompleteBeenSeen={haveExportCompleteBeenSeen}
        >
          <div
            className="flex h-screen flex-col bg-background text-foreground"
            style={{ paddingTop: TITLE_BAR_HEIGHT_PX } as React.CSSProperties}
          >
            {createPortal(<TitleBar />, document.body)}
            <main className="flex min-h-0 flex-1 flex-col pl-6 pr-0">
              <TabHost />
            </main>
        <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
          <SheetContent
            side="right"
            className={cn(
              "flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-0 p-0",
              isTauri() && "!top-[36px] !h-[calc(100vh-36px)]"
            )}
            overlayClassName={isTauri() ? "!top-[36px] left-0 right-0 bottom-0" : undefined}
            overlayStyle={
              isTauri()
                ? { top: TITLE_BAR_HEIGHT, left: 0, right: 0, bottom: 0 }
                : undefined
            }
            onPointerDownOutside={
              isTauri()
                ? (e) => {
                    const orig = (e as { detail?: { originalEvent?: PointerEvent } }).detail?.originalEvent;
                    const target = orig?.target ?? e.target;
                    const targetInTitleBar = target && (target as Element).closest?.("[data-cue-title-bar]");
                    const clientY = orig?.clientY ?? (e as unknown as PointerEvent).clientY;
                    const inTitleBarByPos = typeof clientY === "number" && clientY < TITLE_BAR_HEIGHT;
                    if (!!targetInTitleBar || inTitleBarByPos) e.preventDefault();
                  }
                : undefined
            }
            onInteractOutside={
              isTauri()
                ? (e) => {
                    const orig = (e as { detail?: { originalEvent?: PointerEvent } }).detail?.originalEvent;
                    const target = orig?.target ?? e.target;
                    const targetInTitleBar = target && (target as Element).closest?.("[data-cue-title-bar]");
                    const clientY = orig?.clientY ?? (e as unknown as PointerEvent).clientY;
                    const inTitleBarByPos = typeof clientY === "number" && clientY < TITLE_BAR_HEIGHT;
                    if (!!targetInTitleBar || inTitleBarByPos) e.preventDefault();
                  }
                : undefined
            }
            onOpenAutoFocus={(e) => e.preventDefault()}
          >
            <SheetHeader
              className={cn(
                "relative z-10 shrink-0 overflow-visible px-6 pt-4 pb-4 pr-12 transition-shadow duration-200",
                settingsScrolled &&
                  "shadow-[0_4px_12px_-4px_rgba(0,0,0,0.2)] dark:shadow-[0_4px_12px_-4px_rgba(0,0,0,0.5)]"
              )}
            >
              <SheetTitle id="settings-dialog-title">
                <span
                  role="button"
                  tabIndex={0}
                  data-cursor-default
                  className="outline-none"
                  onClick={() => {
                    settingsTapCountRef.current += 1;
                    if (settingsTapCountRef.current >= 7) {
                      setDiagnosticsRevealed(true);
                      pushToast(
                        "Diagnostics section is now visible at the bottom of Settings.",
                        ""
                      );
                      settingsTapCountRef.current = 0;
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      settingsTapCountRef.current += 1;
                      if (settingsTapCountRef.current >= 7) {
                        setDiagnosticsRevealed(true);
                        pushToast(
                          "Diagnostics section is now visible at the bottom of Settings.",
                          ""
                        );
                        settingsTapCountRef.current = 0;
                      }
                    }
                  }}
                >
                  Settings
                </span>
              </SheetTitle>
            </SheetHeader>
            <div className="relative flex min-h-0 flex-1 flex-col">
              <ScrollArea
                ref={settingsScrollRef}
                type="always"
                className="min-h-0 flex-1"
              >
                {/* Padding ≥40px so card shadow has room; no negative margin (would pull content back to clip edge). */}
                <div className="min-h-full px-6">
                  <Suspense fallback={<EngineSkeletonLoader variant="settings" />}>
                    <Settings />
                  </Suspense>
                </div>
              </ScrollArea>
            </div>
          </SheetContent>
        </Sheet>
        {toasts.length > 0 && (
          <div className="pointer-events-none fixed bottom-4 left-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2">
            {toasts.map((toast) => (
              <div
                key={toast.id}
                className="pointer-events-auto rounded-lg border border-border bg-card p-4 shadow transition-colors duration-200"
                role="status"
                aria-live="polite"
              >
                <div
                  className={`flex items-start justify-between gap-2 ${toast.message || (toast.actions && toast.actions.length > 0) ? "mb-1" : ""}`}
                >
                  <p className="m-0 text-sm font-semibold text-foreground">{toast.title}</p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    aria-label="Dismiss notification"
                    onClick={() => removeToast(toast.id)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                {toast.message ? (
                  <p className="text-xs text-muted-foreground">{toast.message}</p>
                ) : null}
                {toast.actions && toast.actions.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {toast.actions.map((action, i) => (
                      <Button
                        key={i}
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          action.onClick();
                          removeToast(toast.id);
                        }}
                      >
                        {action.label}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
          </div>
          </ToastProvider>
        </SettingsProvider>
        </WorkbenchTabsProvider>
      </RunningJobsProvider>
      </CalibrationProvider>
    </DeviceInfoProvider>
  );
};

export default AppLayout;
