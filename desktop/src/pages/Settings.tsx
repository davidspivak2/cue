import {
  Box,
  Button,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Slider,
  Stack,
  Switch,
  Typography
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";

const BACKEND_HEALTH_URL = "http://127.0.0.1:8765/health";
const BACKEND_TIMEOUT_MS = 1500;

const Settings = () => {
  const [gpuEnabled, setGpuEnabled] = useState(false);
  const [fontSize, setFontSize] = useState(16);
  const [density, setDensity] = useState("comfortable");
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "not_running">(
    "checking"
  );
  const [backendVersion, setBackendVersion] = useState<string | null>(null);

  const checkBackend = useCallback(async () => {
    setBackendStatus("checking");
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

    try {
      const response = await fetch(BACKEND_HEALTH_URL, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`Backend health check failed: ${response.status}`);
      }
      const payload = (await response.json()) as { version?: string };
      setBackendVersion(typeof payload.version === "string" ? payload.version : null);
      setBackendStatus("connected");
    } catch (error) {
      setBackendVersion(null);
      setBackendStatus("not_running");
    } finally {
      window.clearTimeout(timeoutId);
    }
  }, []);

  useEffect(() => {
    void checkBackend();
  }, [checkBackend]);

  return (
    <Stack spacing={4} maxWidth={520}>
      <Box>
        <Typography variant="h5" gutterBottom>
          Settings
        </Typography>
        <Typography color="text.secondary">
          Placeholder controls to preview the UI theme.
        </Typography>
      </Box>
      <FormControlLabel
        control={
          <Switch
            checked={gpuEnabled}
            onChange={(event) => setGpuEnabled(event.target.checked)}
          />
        }
        label="Enable GPU (placeholder)"
      />
      <Box>
        <Typography gutterBottom>Subtitle font size (placeholder)</Typography>
        <Slider
          value={fontSize}
          min={12}
          max={28}
          step={1}
          valueLabelDisplay="auto"
          onChange={(_, value) => setFontSize(value as number)}
        />
      </Box>
      <FormControl fullWidth>
        <InputLabel id="theme-density-label">Theme density (placeholder)</InputLabel>
        <Select
          labelId="theme-density-label"
          value={density}
          label="Theme density (placeholder)"
          onChange={(event) => setDensity(event.target.value)}
        >
          <MenuItem value="comfortable">Comfortable</MenuItem>
          <MenuItem value="compact">Compact</MenuItem>
          <MenuItem value="spacious">Spacious</MenuItem>
        </Select>
      </FormControl>
      <Box>
        <Typography variant="h6" gutterBottom>
          Backend
        </Typography>
        <Stack spacing={1}>
          <Typography>
            Status:{" "}
            <Box
              component="span"
              color={backendStatus === "connected" ? "success.main" : "text.secondary"}
              fontWeight={600}
            >
              {backendStatus === "connected" ? "Connected" : "Not running"}
            </Box>
          </Typography>
          {backendStatus === "connected" ? (
            <Typography color="text.secondary">
              Version: {backendVersion ?? "unknown"}
            </Typography>
          ) : (
            <Typography color="text.secondary">
              Run scripts\\run_backend_dev.cmd
            </Typography>
          )}
          <Box>
            <Button
              variant="outlined"
              size="small"
              onClick={checkBackend}
              disabled={backendStatus === "checking"}
            >
              Check now
            </Button>
          </Box>
        </Stack>
      </Box>
    </Stack>
  );
};

export default Settings;
