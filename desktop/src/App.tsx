import { useEffect } from "react";
import { useTheme } from "next-themes";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { isTauri } from "@tauri-apps/api/core";
import AppLayout from "./components/AppLayout";
import ProjectHub from "./pages/ProjectHub";
import Workbench from "./pages/Workbench";

/** Syncs favicon and Tauri window icon with resolved theme. */
function ThemeIconSync() {
  const { resolvedTheme } = useTheme();
  useEffect(() => {
    const favicon = document.getElementById("favicon") as HTMLLinkElement | null;
    if (favicon) {
      favicon.href = resolvedTheme === "dark" ? "/dark.svg" : "/light.svg";
    }
    if (isTauri() && resolvedTheme) {
      const iconName = resolvedTheme === "dark" ? "dark" : "light";
      const url = `/icons/${iconName}-32.png`;
      fetch(url)
        .then((r) => r.arrayBuffer())
        .then((buf) => getCurrentWindow().setIcon(buf))
        .catch(() => {});
    }
  }, [resolvedTheme]);
  return null;
}

const App = () => {
  return (
    <BrowserRouter>
      <ThemeIconSync />
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<ProjectHub />} />
          <Route path="workbench/:projectId" element={<Workbench />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
