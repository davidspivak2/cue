import { AppBar, Box, IconButton, Toolbar, Tooltip, Typography } from "@mui/material";
import SettingsIcon from "@mui/icons-material/Settings";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useProjects } from "../store/projectsContext";

const AppLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { hasActiveJob } = useProjects();
  const settingsDisabled = hasActiveJob;
  const isSettings = location.pathname.startsWith("/settings");

  return (
    <Box sx={{ minHeight: "100vh", backgroundColor: "background.default" }}>
      <AppBar position="sticky" elevation={0}>
        <Toolbar sx={{ justifyContent: "space-between" }}>
          <Typography variant="h6" fontWeight={600}>
            Cue
          </Typography>
          <Tooltip title="Settings">
            <span>
              <IconButton
                color="inherit"
                onClick={() => navigate("/settings")}
                disabled={settingsDisabled || isSettings}
              >
                <SettingsIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ px: 4, py: 3 }}>
        <Outlet />
      </Box>
    </Box>
  );
};

export default AppLayout;
