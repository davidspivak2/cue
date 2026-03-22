import * as React from "react";
import { isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const SPLASH_DISMISSED_KEY = "cue-splash-dismissed";

function getSplashAlreadyDismissedThisSession(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return sessionStorage.getItem(SPLASH_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

type EngineExtractProgressPayload = {
  label: string;
  index: number;
  total: number;
  phase: string;
};

type AppSplashContextValue = {
  showSplash: boolean;
  setShowSplash: (value: boolean) => void;
  splashDetail: string | null;
  setSplashDetail: (value: string | null) => void;
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
  const [splashDetail, setSplashDetail] = React.useState<string | null>(null);
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

  React.useEffect(() => {
    if (!isTauri()) {
      return;
    }
    let cancelled = false;
    let unlisten: (() => void) | undefined;
    void listen<EngineExtractProgressPayload>("engine-extract-progress", (event) => {
      const p = event.payload;
      if (p.phase === "error") {
        setSplashDetail(p.label);
        return;
      }
      if (p.phase === "start" || p.phase === "part_done" || p.phase === "done") {
        setSplashDetail(p.label);
      }
    }).then((fn) => {
      if (!cancelled) {
        unlisten = fn;
      }
    });
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  const value = React.useMemo(
    () => ({ showSplash, setShowSplash, splashDetail, setSplashDetail }),
    [showSplash, setShowSplash, splashDetail]
  );

  return (
    <AppSplashContext.Provider value={value}>
      {children}
    </AppSplashContext.Provider>
  );
};
