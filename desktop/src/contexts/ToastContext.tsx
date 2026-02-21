import * as React from "react";

export type ToastAction = {
  label: string;
  onClick: () => void;
};

export type ToastOptions = {
  actions?: ToastAction[];
};

export type PushToastFn = (
  title: string,
  message: string,
  options?: ToastOptions
) => void;

export type MarkExportCompleteSeenFn = (
  projectId: string,
  outputPath: string,
  exportedAt: string
) => void;

export type HaveExportCompleteBeenSeenFn = (
  projectId: string,
  outputPath: string,
  exportedAt: string
) => boolean;

type ToastContextValue = {
  pushToast: PushToastFn;
  markExportCompleteSeen: MarkExportCompleteSeenFn;
  haveExportCompleteBeenSeen: HaveExportCompleteBeenSeenFn;
};

const ToastContext = React.createContext<ToastContextValue | null>(null);

export const useToast = (): ToastContextValue => {
  const ctx = React.useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
};

export const ToastProvider = ({
  children,
  pushToast,
  markExportCompleteSeen,
  haveExportCompleteBeenSeen
}: {
  children: React.ReactNode;
  pushToast: PushToastFn;
  markExportCompleteSeen: MarkExportCompleteSeenFn;
  haveExportCompleteBeenSeen: HaveExportCompleteBeenSeenFn;
}) => (
  <ToastContext.Provider
    value={{ pushToast, markExportCompleteSeen, haveExportCompleteBeenSeen }}
  >
    {children}
  </ToastContext.Provider>
);
