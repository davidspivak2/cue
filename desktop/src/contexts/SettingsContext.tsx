import * as React from "react";

type SettingsContextValue = {
  openSettings: () => void;
  closeSettings: () => void;
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
  closeSettings,
  settingsOpen
}: {
  children: React.ReactNode;
  openSettings: () => void;
  closeSettings: () => void;
  settingsOpen: boolean;
}) => (
  <SettingsContext.Provider value={{ openSettings, closeSettings, settingsOpen }}>
    {children}
  </SettingsContext.Provider>
);
