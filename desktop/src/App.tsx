import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import ProjectHub from "./pages/ProjectHub";
import Workbench from "./pages/Workbench";
import Settings from "./pages/Settings";
import { NavigationProvider } from "./store/navigationContext";
import { ProjectsProvider } from "./store/projectsContext";

const App = () => (
  <ProjectsProvider>
    <NavigationProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<ProjectHub />} />
            <Route path="workbench" element={<Workbench />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </NavigationProvider>
  </ProjectsProvider>
);

export default App;
