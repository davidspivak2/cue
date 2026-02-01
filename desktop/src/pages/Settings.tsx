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
  TextField,
  Typography
} from "@mui/material";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type JobKind = "pipeline" | "demo";

type JobEvent = {
  job_id: string;
  ts: string;
  type: "started" | "step" | "progress" | "completed" | "cancelled" | "error";
  step?: string;
  message?: string;
  pct?: number;
  status?: string;
};

type JobRequest = {
  kind: JobKind;
  input_path?: string;
  output_dir?: string;
  options?: Record<string, unknown>;
};

const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const BACKEND_HEALTH_URL = "http://127.0.0.1:8765/health";
const JOBS_URL = `${BACKEND_BASE_URL}/jobs`;
const BACKEND_TIMEOUT_MS = 1500;

const Settings = () => {
  const [gpuEnabled, setGpuEnabled] = useState(false);
  const [fontSize, setFontSize] = useState(16);
  const [density, setDensity] = useState("comfortable");
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "not_running">(
    "checking"
  );
  const [backendVersion, setBackendVersion] = useState<string | null>(null);
  const [jobKind, setJobKind] = useState<JobKind>("pipeline");
  const [inputPath, setInputPath] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState("idle");
  const [latestStep, setLatestStep] = useState<string | null>(null);
  const [latestMessage, setLatestMessage] = useState<string | null>(null);
  const [latestProgress, setLatestProgress] = useState<number | null>(null);
  const [jobEvents, setJobEvents] = useState<JobEvent[]>([]);
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

  const handleJobEvent = useCallback(
    (event: JobEvent) => {
      setJobEvents((prev) => {
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
        setJobStatus("running");
      }

      if (["completed", "cancelled", "error"].includes(event.type)) {
        setJobStatus(event.status ?? event.type);
        closeEventSource();
      }
    },
    [closeEventSource]
  );

  const startJob = useCallback(async () => {
    closeEventSource();
    setJobId(null);
    setJobStatus("queued");
    setLatestStep(null);
    setLatestMessage(null);
    setLatestProgress(null);
    setJobEvents([]);

    try {
      const requestBody: JobRequest = { kind: jobKind, options: {} };
      if (jobKind === "pipeline") {
        requestBody.input_path = inputPath.trim();
        requestBody.output_dir = outputDir.trim();
      }

      const response = await fetch(JOBS_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody)
      });
      if (!response.ok) {
        throw new Error(`Failed to start job: ${response.status}`);
      }
      const payload = (await response.json()) as { job_id?: string; events_url?: string };
      if (!payload.job_id) {
        throw new Error("Job response missing job_id");
      }
      setJobId(payload.job_id);

      const eventsUrl = payload.events_url ?? `${JOBS_URL}/${payload.job_id}/events`;
      const source = new EventSource(eventsUrl);
      eventSourceRef.current = source;

      source.onmessage = (messageEvent) => {
        try {
          const data = JSON.parse(messageEvent.data) as JobEvent;
          handleJobEvent(data);
        } catch (error) {
          setJobEvents((prev) => [
            ...prev,
            {
              job_id: payload.job_id ?? "unknown",
              ts: new Date().toISOString(),
              type: "error",
              message: "Failed to parse event stream message.",
              status: "error"
            }
          ]);
          setJobStatus("error");
          closeEventSource();
        }
      };

      source.onerror = () => {
        setJobStatus("error");
        closeEventSource();
      };
    } catch (error) {
      setJobStatus("error");
    }
  }, [closeEventSource, handleJobEvent, inputPath, jobKind, outputDir]);

  const cancelJob = useCallback(async () => {
    if (!jobId) {
      return;
    }
    try {
      const response = await fetch(`${JOBS_URL}/${jobId}/cancel`, { method: "POST" });
      if (response.ok) {
        const payload = (await response.json()) as { status?: string };
        setJobStatus(payload.status ?? "cancel_requested");
      } else {
        setJobStatus("error");
      }
    } catch (error) {
      setJobStatus("error");
    }
  }, [jobId]);

  const clearJobEvents = useCallback(() => {
    setJobEvents([]);
    setLatestStep(null);
    setLatestMessage(null);
    setLatestProgress(null);
  }, []);

  const jobIsRunning = useMemo(
    () => ["queued", "running"].includes(jobStatus),
    [jobStatus]
  );
  const pipelineInputsMissing = useMemo(
    () =>
      jobKind === "pipeline" &&
      (!inputPath.trim().length || !outputDir.trim().length),
    [inputPath, jobKind, outputDir]
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
          Jobs
        </Typography>
        <Stack spacing={2}>
          <FormControl fullWidth>
            <InputLabel id="job-kind-label">Job type</InputLabel>
            <Select
              labelId="job-kind-label"
              value={jobKind}
              label="Job type"
              onChange={(event) => setJobKind(event.target.value as JobKind)}
            >
              <MenuItem value="pipeline">Pipeline job</MenuItem>
              <MenuItem value="demo">Demo job</MenuItem>
            </Select>
          </FormControl>
          {jobKind === "pipeline" ? (
            <Stack spacing={1.5}>
              <TextField
                label="Input file path"
                value={inputPath}
                onChange={(event) => setInputPath(event.target.value)}
                placeholder="C:\\path\\to\\video.mp4"
                required
                error={pipelineInputsMissing && !inputPath.trim().length}
                helperText={
                  pipelineInputsMissing && !inputPath.trim().length
                    ? "Input path is required for pipeline jobs."
                    : " "
                }
              />
              <TextField
                label="Output directory path"
                value={outputDir}
                onChange={(event) => setOutputDir(event.target.value)}
                placeholder="C:\\Cue_output"
                required
                error={pipelineInputsMissing && !outputDir.trim().length}
                helperText={
                  pipelineInputsMissing && !outputDir.trim().length
                    ? "Output directory is required for pipeline jobs."
                    : " "
                }
              />
            </Stack>
          ) : (
            <Typography color="text.secondary">
              Demo jobs emit fake step/progress events for UI testing.
            </Typography>
          )}
          {backendStatus !== "connected" ? (
            <Typography color="text.secondary">
              Run scripts\\run_backend_dev.cmd to start the backend.
            </Typography>
          ) : null}
          <Stack direction="row" spacing={2} alignItems="center">
            <Button
              variant="contained"
              onClick={startJob}
              disabled={
                jobIsRunning || backendStatus !== "connected" || pipelineInputsMissing
              }
            >
              Start job
            </Button>
            <Button
              variant="outlined"
              color="warning"
              onClick={cancelJob}
              disabled={!jobIsRunning}
            >
              Cancel
            </Button>
            <Button variant="text" onClick={clearJobEvents}>
              Clear
            </Button>
          </Stack>
          <Stack spacing={0.5}>
            <Typography>
              Status:{" "}
              <Box component="span" fontWeight={600}>
                {jobStatus}
              </Box>
            </Typography>
            {jobId ? (
              <Typography color="text.secondary">Job ID: {jobId}</Typography>
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
              {jobEvents.length === 0 ? (
                <Typography color="text.secondary">No events yet.</Typography>
              ) : (
                jobEvents.map((event, index) => (
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
