import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import ProjectHub from "./pages/ProjectHub";
import Workbench from "./pages/Workbench";

const App = () => {
  return (
    <BrowserRouter>
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
