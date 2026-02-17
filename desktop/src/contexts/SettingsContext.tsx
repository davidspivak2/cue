import * as React from "react";

type SettingsContextValue = {
  openSettings: () => void;
};

const SettingsContext = React.createContext<SettingsContextValue | null>(null);

export const useSettings = (): SettingsContextValue => {
  const ctx = React.useContext(SettingsContext);
  if (!ctx) {
    throw new Error("useSettings must be used within a SettingsProvider");
  }
  return ctx;
};

export const SettingsProvider = ({
  children,
  openSettings
}: {
  children: React.ReactNode;
  openSettings: () => void;
}) => (
  <SettingsContext.Provider value={{ openSettings }}>
    {children}
  </SettingsContext.Provider>
);
