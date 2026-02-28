import * as React from "react";

const SPLASH_DISMISSED_KEY = "cue-splash-dismissed";

function getSplashAlreadyDismissedThisSession(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return sessionStorage.getItem(SPLASH_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

type AppSplashContextValue = {
  showSplash: boolean;
  setShowSplash: (value: boolean) => void;
};

const AppSplashContext = React.createContext<AppSplashContextValue | null>(null);

export const useAppSplash = (): AppSplashContextValue => {
  const ctx = React.useContext(AppSplashContext);
  if (!ctx) {
    throw new Error("useAppSplash must be used within AppSplashProvider");
  }
  return ctx;
};

export const AppSplashProvider = ({ children }: { children: React.ReactNode }) => {
  const [showSplash, setShowSplashState] = React.useState(
    () => !getSplashAlreadyDismissedThisSession()
  );
  const dismissedRef = React.useRef(getSplashAlreadyDismissedThisSession());

  const setShowSplash = React.useCallback((value: boolean) => {
    if (value && dismissedRef.current) return;
    if (!value) {
      dismissedRef.current = true;
      try {
        sessionStorage.setItem(SPLASH_DISMISSED_KEY, "1");
      } catch {
        /* ignore */
      }
    }
    setShowSplashState(value);
  }, []);

  const value = React.useMemo(
    () => ({ showSplash, setShowSplash }),
    [showSplash, setShowSplash]
  );

  return (
    <AppSplashContext.Provider value={value}>
      {children}
    </AppSplashContext.Provider>
  );
};
