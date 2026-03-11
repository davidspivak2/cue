import { Suspense, useEffect, useRef } from "react";
import { useTheme } from "next-themes";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { isTauri } from "@tauri-apps/api/core";
import { Loader2 } from "lucide-react";
import AppLayout from "./components/AppLayout";
import AppSplash from "./components/AppSplash";
import { AppSplashProvider } from "./contexts/AppSplashContext";
import { waitForBackendHealthy } from "./backendHealth";
import {
  normalizeInterfaceScale,
  readStoredInterfaceScale,
  setLocalInterfaceScale,
  stepInterfaceScale
} from "./lib/interfaceScale";
import { fetchSettings, updateSettings } from "./settingsClient";

/** Syncs favicon with in-app theme; taskbar/window icon with system theme only. */
function ThemeIconSync() {
  const { resolvedTheme } = useTheme();

  // Favicon follows in-app theme (tab/window title area).
  useEffect(() => {
    const favicon = document.getElementById("favicon") as HTMLLinkElement | null;
    if (favicon) {
      favicon.href = resolvedTheme === "dark" ? "/dark.svg" : "/light.svg";
    }
  }, [resolvedTheme]);

  // Taskbar/window icon follows system theme only (not in-app theme).
  useEffect(() => {
    if (!isTauri()) return;
    try {
      if (typeof window.matchMedia !== "function") return;
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      const setWindowIcon = () => {
        const iconName = media.matches ? "dark" : "light";
        const url = `/icons/${iconName}-32.png`;
        fetch(url)
          .then((r) => r.arrayBuffer())
          .then((buf) => getCurrentWindow().setIcon(buf))
          .catch(() => {});
      };
      setWindowIcon();

      if (typeof media.addEventListener === "function") {
        media.addEventListener("change", setWindowIcon);
        return () => media.removeEventListener("change", setWindowIcon);
      }

      if (typeof media.addListener === "function") {
        media.addListener(setWindowIcon);
        return () => media.removeListener(setWindowIcon);
      }
    } catch {
      return;
    }

    return;
  }, []);
  return null;
}

function InterfaceScaleSync() {
  const persistTimerRef = useRef<number | null>(null);
  const pendingScaleRef = useRef(readStoredInterfaceScale());
  const lastWheelStepAtRef = useRef(0);

  useEffect(() => {
    let active = true;
    const queuePersist = (scale: number) => {
      pendingScaleRef.current = normalizeInterfaceScale(scale);
      if (persistTimerRef.current !== null) {
        window.clearTimeout(persistTimerRef.current);
      }
      persistTimerRef.current = window.setTimeout(() => {
        void (async () => {
          try {
            const next = await updateSettings({
              interface_scale: pendingScaleRef.current
            });
            if (!active) {
              return;
            }
            setLocalInterfaceScale(next.interface_scale, "backend-sync");
          } catch {
            // Keep the local value if the backend save fails.
          }
        })();
      }, 180);
    };

    const handleWheel = (event: WheelEvent) => {
      if (!event.ctrlKey || event.deltaY === 0) {
        return;
      }
      // Override browser zoom so Ctrl+wheel steps through Cue's interface sizes instead.
      event.preventDefault();
      const now = Date.now();
      if (now - lastWheelStepAtRef.current < 120) {
        return;
      }
      lastWheelStepAtRef.current = now;
      const currentScale = readStoredInterfaceScale();
      const nextScale = stepInterfaceScale(currentScale, event.deltaY < 0 ? 1 : -1);
      if (nextScale === currentScale) {
        return;
      }
      setLocalInterfaceScale(nextScale, "shortcut");
      queuePersist(nextScale);
    };

    const run = async () => {
      try {
        await waitForBackendHealthy();
        if (!active) {
          return;
        }
        const settings = await fetchSettings();
        if (!active) {
          return;
        }
        const scale = normalizeInterfaceScale(settings.interface_scale);
        pendingScaleRef.current = scale;
        setLocalInterfaceScale(scale, "backend-sync");
      } catch {
        // Keep the cached scale if settings are not reachable yet.
      }
    };
    window.addEventListener("wheel", handleWheel, { passive: false });
    void run();
    return () => {
      active = false;
      if (persistTimerRef.current !== null) {
        window.clearTimeout(persistTimerRef.current);
      }
      window.removeEventListener("wheel", handleWheel);
    };
  }, []);

  return null;
}

function RouteFallback() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-muted-foreground">
      <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
      <p className="text-sm">Loading...</p>
    </div>
  );
}

const App = () => {
  return (
    <AppSplashProvider>
      <AppSplash />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ThemeIconSync />
        <InterfaceScaleSync />
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/*" element={<AppLayout />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AppSplashProvider>
  );
};

export default App;
