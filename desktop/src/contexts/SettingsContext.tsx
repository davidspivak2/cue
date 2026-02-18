import * as React from "react";

type SettingsContextValue = {
  openSettings: () => void;
  settingsOpen: boolean;
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
  openSettings,
  settingsOpen
}: {
  children: React.ReactNode;
  openSettings: () => void;
  settingsOpen: boolean;
}) => (
  <SettingsContext.Provider value={{ openSettings, settingsOpen }}>
    {children}
  </SettingsContext.Provider>
);
