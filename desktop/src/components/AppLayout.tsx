import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { isTauri } from "@tauri-apps/api/core";

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
import { SettingsProvider } from "@/contexts/SettingsContext";
import { ToastProvider } from "@/contexts/ToastContext";
import Settings from "@/pages/Settings";
import { fetchProjects } from "@/projectsClient";
import { WorkbenchTabsProvider } from "@/workbenchTabs";

const ACTIVE_TASK_POLL_MS = 2500;
const IDLE_TASK_POLL_MS = 10000;

type ToastItem = {
  id: string;
  title: string;
  message: string;
};

const AppLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const hasLaunchedRef = React.useRef(false);
  const seenNoticeIdsRef = React.useRef<Set<string>>(new Set());
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const openSettings = React.useCallback(() => setSettingsOpen(true), []);

  const removeToast = React.useCallback((toastId: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== toastId));
  }, []);

  const pushToast = React.useCallback(
    (title: string, message: string) => {
      const toastId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setToasts((prev) => [...prev, { id: toastId, title, message }].slice(-4));
      window.setTimeout(() => {
        removeToast(toastId);
      }, 8000);
    },
    [removeToast]
  );

  React.useEffect(() => {
    if (hasLaunchedRef.current) {
      return;
    }
    hasLaunchedRef.current = true;
    if (location.pathname !== "/") {
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
          const title = notice.status === "cancelled" ? "Task cancelled" : "Task failed";
          const projectTitle = project.title || "Video";
          pushToast(projectTitle, `${title}: ${notice.message}`);
        }
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
    <WorkbenchTabsProvider>
      <SettingsProvider openSettings={openSettings} settingsOpen={settingsOpen}>
        <ToastProvider pushToast={pushToast}>
          <div
            className="min-h-screen bg-background text-foreground"
            style={
              isTauri()
                ? ({ paddingTop: TITLE_BAR_HEIGHT_PX } as React.CSSProperties)
                : undefined
            }
          >
            {createPortal(<TitleBar />, document.body)}
            <main className="flex-1 px-6 py-6">
              <Outlet />
            </main>
        <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
          <SheetContent
            side="right"
            className={cn(
              "flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-4 p-0",
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
            <SheetHeader className="shrink-0 px-6 pt-4 pb-0 pr-12">
              <SheetTitle id="settings-dialog-title">Settings</SheetTitle>
            </SheetHeader>
            <ScrollArea type="always" className="min-h-0 flex-1 px-6 pb-6 pr-4">
              <Settings />
            </ScrollArea>
          </SheetContent>
        </Sheet>
        {toasts.length > 0 && (
          <div className="pointer-events-none fixed bottom-4 left-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2">
            {toasts.map((toast) => (
              <div
                key={toast.id}
                className="pointer-events-auto rounded-md border border-border bg-card p-3 shadow-lg"
                role="status"
                aria-live="polite"
              >
                <div className="mb-1 flex items-start justify-between gap-2">
                  <p className="text-sm font-semibold text-foreground">{toast.title}</p>
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
                <p className="text-xs text-muted-foreground">{toast.message}</p>
              </div>
            ))}
          </div>
        )}
          </div>
        </ToastProvider>
      </SettingsProvider>
    </WorkbenchTabsProvider>
  );
};

export default AppLayout;
