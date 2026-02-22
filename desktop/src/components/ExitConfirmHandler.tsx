import * as React from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { useRunningJobs } from "@/contexts/RunningJobsContext";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import type { RunningJob } from "@/contexts/RunningJobsContext";

export function ExitConfirmHandler() {
  const { getRunningJobs } = useRunningJobs();
  const [open, setOpen] = React.useState(false);
  const [pendingJobs, setPendingJobs] = React.useState<RunningJob[]>([]);
  const [exiting, setExiting] = React.useState(false);

  React.useEffect(() => {
    if (!isTauri()) return;
    const unlisten = listen("close-requested", () => {
      const jobs = getRunningJobs();
      if (jobs.length === 0) {
        void invoke("allow_exit_and_close");
      } else {
        setPendingJobs(jobs);
        setOpen(true);
      }
    });
    return () => {
      void unlisten.then((fn) => fn());
    };
  }, [getRunningJobs]);

  const handleCancel = React.useCallback(() => {
    setOpen(false);
    setPendingJobs([]);
  }, []);

  const handleExitAnyway = React.useCallback(async () => {
    setExiting(true);
    try {
      await Promise.all(pendingJobs.map((j) => j.cancel()));
      await invoke("allow_exit_and_close");
    } finally {
      setExiting(false);
      setOpen(false);
      setPendingJobs([]);
    }
  }, [pendingJobs]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleCancel()}>
      <DialogContent
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => {
          handleCancel();
          e.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>Exit and cancel tasks?</DialogTitle>
          <DialogDescription>
            The following tasks are still running. If you exit now they will be cancelled.
          </DialogDescription>
        </DialogHeader>
        <ul className="list-inside list-disc text-sm text-muted-foreground">
          {pendingJobs.map((j) => (
            <li key={j.id}>{j.label}</li>
          ))}
        </ul>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={handleCancel}>
            Stay
          </Button>
          <Button type="button" variant="destructive" onClick={() => void handleExitAnyway()} disabled={exiting}>
            {exiting ? "Cancelling…" : "Exit anyway"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
