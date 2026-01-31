import {
  Box,
  Button,
  FormControl,
  FormControlLabel,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Slider,
  Stack,
  Switch,
  Typography
} from "@mui/material";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type DemoJobEvent = {
  job_id: string;
  ts: string;
  type: "started" | "step" | "progress" | "completed" | "cancelled" | "error";
  step?: string;
  message?: string;
  pct?: number;
  status?: string;
};

const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const BACKEND_HEALTH_URL = "http://127.0.0.1:8765/health";
const DEMO_JOB_URL = `${BACKEND_BASE_URL}/jobs`;
const BACKEND_TIMEOUT_MS = 1500;

const Settings = () => {
  const [gpuEnabled, setGpuEnabled] = useState(false);
  const [fontSize, setFontSize] = useState(16);
  const [density, setDensity] = useState("comfortable");
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "not_running">(
    "checking"
  );
  const [backendVersion, setBackendVersion] = useState<string | null>(null);
  const [demoJobId, setDemoJobId] = useState<string | null>(null);
  const [demoStatus, setDemoStatus] = useState("idle");
  const [latestStep, setLatestStep] = useState<string | null>(null);
  const [latestMessage, setLatestMessage] = useState<string | null>(null);
  const [latestProgress, setLatestProgress] = useState<number | null>(null);
  const [demoEvents, setDemoEvents] = useState<DemoJobEvent[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

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

  const closeEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      closeEventSource();
    };
  }, [closeEventSource]);

  const handleDemoEvent = useCallback(
    (event: DemoJobEvent) => {
      setDemoEvents((prev) => {
        const next = [...prev, event];
        return next.length > 200 ? next.slice(next.length - 200) : next;
      });

      if (event.type === "step") {
        setLatestStep(event.step ?? null);
        setLatestMessage(event.message ?? null);
      }

      if (event.type === "progress") {
        setLatestProgress(typeof event.pct === "number" ? event.pct : null);
        if (event.message) {
          setLatestMessage(event.message);
        }
      }

      if (event.type === "started") {
        setDemoStatus("running");
      }

      if (["completed", "cancelled", "error"].includes(event.type)) {
        setDemoStatus(event.status ?? event.type);
        closeEventSource();
      }
    },
    [closeEventSource]
  );

  const startDemoJob = useCallback(async () => {
    closeEventSource();
    setDemoJobId(null);
    setDemoStatus("queued");
    setLatestStep(null);
    setLatestMessage(null);
    setLatestProgress(null);
    setDemoEvents([]);

    try {
      const response = await fetch(DEMO_JOB_URL, { method: "POST" });
      if (!response.ok) {
        throw new Error(`Failed to start demo job: ${response.status}`);
      }
      const payload = (await response.json()) as { job_id?: string; events_url?: string };
      if (!payload.job_id) {
        throw new Error("Demo job response missing job_id");
      }
      setDemoJobId(payload.job_id);

      const eventsUrl = payload.events_url ?? `${DEMO_JOB_URL}/${payload.job_id}/events`;
      const source = new EventSource(eventsUrl);
      eventSourceRef.current = source;

      source.onmessage = (messageEvent) => {
        try {
          const data = JSON.parse(messageEvent.data) as DemoJobEvent;
          handleDemoEvent(data);
        } catch (error) {
          setDemoEvents((prev) => [
            ...prev,
            {
              job_id: payload.job_id ?? "unknown",
              ts: new Date().toISOString(),
              type: "error",
              message: "Failed to parse event stream message.",
              status: "error"
            }
          ]);
          setDemoStatus("error");
          closeEventSource();
        }
      };

      source.onerror = () => {
        setDemoStatus("error");
        closeEventSource();
      };
    } catch (error) {
      setDemoStatus("error");
    }
  }, [closeEventSource, handleDemoEvent]);

  const cancelDemoJob = useCallback(async () => {
    if (!demoJobId) {
      return;
    }
    try {
      const response = await fetch(`${DEMO_JOB_URL}/${demoJobId}/cancel`, { method: "POST" });
      if (response.ok) {
        const payload = (await response.json()) as { status?: string };
        setDemoStatus(payload.status ?? "cancel_requested");
      } else {
        setDemoStatus("error");
      }
    } catch (error) {
      setDemoStatus("error");
    }
  }, [demoJobId]);

  const clearDemoEvents = useCallback(() => {
    setDemoEvents([]);
    setLatestStep(null);
    setLatestMessage(null);
    setLatestProgress(null);
  }, []);

  const demoIsRunning = useMemo(
    () => ["queued", "running"].includes(demoStatus),
    [demoStatus]
  );

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
      <Box>
        <Typography variant="h6" gutterBottom>
          Demo Job
        </Typography>
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} alignItems="center">
            <Button variant="contained" onClick={startDemoJob} disabled={demoIsRunning}>
              Start demo job
            </Button>
            <Button
              variant="outlined"
              color="warning"
              onClick={cancelDemoJob}
              disabled={!demoIsRunning}
            >
              Cancel
            </Button>
            <Button variant="text" onClick={clearDemoEvents}>
              Clear
            </Button>
          </Stack>
          <Stack spacing={0.5}>
            <Typography>
              Status:{" "}
              <Box component="span" fontWeight={600}>
                {demoStatus}
              </Box>
            </Typography>
            {demoJobId ? (
              <Typography color="text.secondary">Job ID: {demoJobId}</Typography>
            ) : null}
            {latestStep ? (
              <Typography color="text.secondary">
                Step: {latestStep}
                {latestMessage ? ` — ${latestMessage}` : null}
              </Typography>
            ) : null}
            {typeof latestProgress === "number" ? (
              <Stack spacing={1}>
                <Typography color="text.secondary">Progress: {latestProgress}%</Typography>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(100, Math.max(0, latestProgress))}
                />
              </Stack>
            ) : null}
          </Stack>
          <Box
            sx={{
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
              maxHeight: 200,
              overflowY: "auto",
              p: 1.5
            }}
          >
            <Stack spacing={0.5}>
              {demoEvents.length === 0 ? (
                <Typography color="text.secondary">No events yet.</Typography>
              ) : (
                demoEvents.map((event, index) => (
                  <Typography
                    key={`${event.ts}-${event.type}-${index}`}
                    variant="body2"
                    color="text.secondary"
                  >
                    [{event.type}]
                    {event.step ? ` ${event.step}` : ""}{" "}
                    {event.message ? `— ${event.message}` : ""}{" "}
                    {typeof event.pct === "number" ? `(${event.pct}%)` : ""}
                  </Typography>
                ))
              )}
            </Stack>
          </Box>
        </Stack>
      </Box>
    </Stack>
  );
};

export default Settings;
