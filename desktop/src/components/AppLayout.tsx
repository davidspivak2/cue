import * as React from "react";
import { X } from "lucide-react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle
} from "@/components/ui/dialog";
import { SettingsProvider } from "@/contexts/SettingsContext";
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
          const projectTitle = project.title || "Project";
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
      <SettingsProvider openSettings={openSettings}>
        <div className="min-h-screen bg-background text-foreground">
          <main className="flex-1 px-6 py-6">
            <Outlet />
          </main>
        <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
          <DialogContent className="max-h-[85vh] overflow-y-auto">
            <DialogTitle id="settings-dialog-title">Settings</DialogTitle>
            <div className="max-h-[calc(85vh-4rem)] overflow-y-auto">
              <Settings />
            </div>
          </DialogContent>
        </Dialog>
        {toasts.length > 0 && (
          <div className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2">
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
      </SettingsProvider>
    </WorkbenchTabsProvider>
  );
};

export default AppLayout;
