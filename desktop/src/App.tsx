import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import Home from "./pages/Home";
import ProjectHub from "./pages/ProjectHub";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import Workbench from "./pages/Workbench";

const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<ProjectHub />} />
          <Route path="legacy" element={<Home />} />
          <Route path="review" element={<Review />} />
          <Route path="settings" element={<Settings />} />
          <Route path="workbench/:projectId" element={<Workbench />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
