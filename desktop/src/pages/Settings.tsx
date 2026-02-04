import { Stack, Typography } from "@mui/material";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useNavigationStore } from "../store/navigationContext";

const Settings = () => {
  const navigate = useNavigate();
  const { lastNonSettingsRoute } = useNavigationStore();
  const fallbackRoute = lastNonSettingsRoute ?? "/";

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        navigate(fallbackRoute);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [fallbackRoute, navigate]);

  return (
    <Stack spacing={2} maxWidth={640}>
      <Typography variant="h4" fontWeight={600}>
        Settings
      </Typography>
      <Typography color="text.secondary">Settings content will appear here.</Typography>
    </Stack>
  );
};

export default Settings;
