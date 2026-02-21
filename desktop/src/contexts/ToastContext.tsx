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

type ToastContextValue = {
  pushToast: PushToastFn;
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
  pushToast
}: {
  children: React.ReactNode;
  pushToast: PushToastFn;
}) => (
  <ToastContext.Provider value={{ pushToast }}>
    {children}
  </ToastContext.Provider>
);
