import { createContext, useCallback, useContext, useMemo, useState } from "react";

type NavigationContextValue = {
  lastNonSettingsRoute: string | null;
  setLastNonSettingsRoute: (route: string) => void;
};

const NavigationContext = createContext<NavigationContextValue | null>(null);

export const NavigationProvider = ({ children }: { children: React.ReactNode }) => {
  const [lastNonSettingsRoute, setLastRoute] = useState<string | null>(null);

  const setLastNonSettingsRoute = useCallback((route: string) => {
    setLastRoute(route);
  }, []);

  const value = useMemo(
    () => ({
      lastNonSettingsRoute,
      setLastNonSettingsRoute
    }),
    [lastNonSettingsRoute, setLastNonSettingsRoute]
  );

  return <NavigationContext.Provider value={value}>{children}</NavigationContext.Provider>;
};

export const useNavigationStore = () => {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error("useNavigationStore must be used within NavigationProvider");
  }
  return context;
};
