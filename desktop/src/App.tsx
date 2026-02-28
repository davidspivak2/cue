import { Suspense, lazy, useEffect } from "react";
import { useTheme } from "next-themes";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { isTauri } from "@tauri-apps/api/core";
import { Loader2 } from "lucide-react";
import AppLayout from "./components/AppLayout";
import AppSplash from "./components/AppSplash";
import { RouteErrorBoundary } from "./components/RouteErrorBoundary";
import { WorkbenchSkeleton } from "./components/WorkbenchSkeleton";
import { AppSplashProvider } from "./contexts/AppSplashContext";
import ProjectHub from "./pages/ProjectHub";

const Workbench = lazy(() => import("./pages/Workbench"));

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
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<AppLayout />}>
              <Route index element={<ProjectHub />} />
              <Route
                path="workbench/:projectId"
                element={
                  <RouteErrorBoundary>
                    <Suspense fallback={<WorkbenchSkeleton />}>
                      <Workbench />
                    </Suspense>
                  </RouteErrorBoundary>
                }
              />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AppSplashProvider>
  );
};

export default App;
