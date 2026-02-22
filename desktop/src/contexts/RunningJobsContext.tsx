import * as React from "react";

export type RunningJob = {
  id: string;
  label: string;
  cancel: () => Promise<void>;
};

type RunningJobsContextValue = {
  registerJob: (job: RunningJob) => () => void;
  getRunningJobs: () => RunningJob[];
};

const RunningJobsContext = React.createContext<RunningJobsContextValue | null>(null);

export const useRunningJobs = (): RunningJobsContextValue => {
  const ctx = React.useContext(RunningJobsContext);
  if (!ctx) {
    throw new Error("useRunningJobs must be used within a RunningJobsProvider");
  }
  return ctx;
};

export const RunningJobsProvider = ({ children }: { children: React.ReactNode }) => {
  const [jobs, setJobs] = React.useState<RunningJob[]>([]);

  const registerJob = React.useCallback((job: RunningJob) => {
    setJobs((prev) => [...prev.filter((j) => j.id !== job.id), job]);
    return () => {
      setJobs((prev) => prev.filter((j) => j.id !== job.id));
    };
  }, []);

  const getRunningJobs = React.useCallback(() => jobs, [jobs]);

  const value = React.useMemo(
    () => ({ registerJob, getRunningJobs }),
    [registerJob, getRunningJobs]
  );

  return (
    <RunningJobsContext.Provider value={value}>{children}</RunningJobsContext.Provider>
  );
};
