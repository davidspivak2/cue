import * as React from "react";

type ToastContextValue = {
  pushToast: (title: string, message: string) => void;
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
  pushToast: (title: string, message: string) => void;
}) => (
  <ToastContext.Provider value={{ pushToast }}>
    {children}
  </ToastContext.Provider>
);
