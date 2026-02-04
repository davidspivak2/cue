import {
  Box,
  Button,
  Divider,
  IconButton,
  LinearProgress,
  Stack,
  Tab,
  Tabs,
  Typography
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { convertFileSrc } from "@tauri-apps/api/core";
import { useProjects } from "../store/projectsContext";
import { pickVideoFile } from "../store/filePicker";
import { formatDuration } from "../store/utils";

type WorkbenchState =
  | "WB_NEEDS_VIDEO"
  | "WB_VIDEO_LINKED_READY"
  | "WB_CREATING_SUBTITLES"
  | "WB_SUBTITLES_READY"
  | "WB_EXPORTING"
  | "WB_EXPORT_SUCCESS";

const stepLabels: Record<string, string> = {
  validate: "Creating subtitles",
  transcribe: "Creating subtitles",
  align: "Matching individual words to speech",
  export: "Exporting video"
};

const Workbench = () => {
  const navigate = useNavigate();
  const {
    projects,
    openTabs,
    activeTabId,
    openProject,
    closeProject,
    relinkProjectPath,
    startCreateSubtitles,
    cancelCreateSubtitles,
    getRuntime,
    hasActiveJob,
    activeJobProjectId,
    clearRuntimeError
  } = useProjects();
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (openTabs.length === 0) {
      navigate("/");
    }
  }, [navigate, openTabs.length]);

  const activeProject = activeTabId ? projects[activeTabId] : undefined;
  const runtime = activeProject ? getRuntime(activeProject.projectId) : undefined;

  const workbenchState: WorkbenchState = useMemo(() => {
    if (!activeProject) {
      return "WB_NEEDS_VIDEO";
    }
    if (activeProject.status === "Missing file") {
      return "WB_NEEDS_VIDEO";
    }
    if (runtime && ["queued", "running"].includes(runtime.jobStatus)) {
      return "WB_CREATING_SUBTITLES";
    }
    if (activeProject.status === "Ready") {
      return "WB_SUBTITLES_READY";
    }
    if (activeProject.status === "Exporting") {
      return "WB_EXPORTING";
    }
    if (activeProject.status === "Done") {
      return "WB_EXPORT_SUCCESS";
    }
    return "WB_VIDEO_LINKED_READY";
  }, [activeProject, runtime]);

  const busyInOtherProject =
    hasActiveJob && activeJobProjectId && activeJobProjectId !== activeProject?.projectId;
  const actionsDisabled = busyInOtherProject || workbenchState === "WB_CREATING_SUBTITLES";

  useEffect(() => {
    if (workbenchState === "WB_NEEDS_VIDEO" || workbenchState === "WB_CREATING_SUBTITLES") {
      setLeftOpen(false);
      setRightOpen(false);
    }
  }, [workbenchState]);

  const handleRelink = useCallback(async () => {
    if (!activeProject) {
      return;
    }
    const selection = await pickVideoFile();
    if (!selection) {
      return;
    }
    await relinkProjectPath(activeProject.projectId, selection);
  }, [activeProject, relinkProjectPath]);

  const handleCreateSubtitles = useCallback(async () => {
    if (!activeProject) {
      return;
    }
    await startCreateSubtitles(activeProject.projectId);
  }, [activeProject, startCreateSubtitles]);

  const handleCancel = useCallback(async () => {
    if (!activeProject) {
      return;
    }
    await cancelCreateSubtitles(activeProject.projectId);
  }, [activeProject, cancelCreateSubtitles]);

  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!runtime?.startedAt || !["queued", "running"].includes(runtime.jobStatus)) {
      setElapsedSeconds(0);
      return;
    }
    const interval = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - runtime.startedAt!) / 1000));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [runtime?.jobStatus, runtime?.startedAt]);

  const steps = useMemo(() => {
    const currentStep = runtime?.latestStep;
    const keys = ["validate", "transcribe", "align", "export"];
    return keys.map((key) => {
      const label = stepLabels[key] ?? key;
      let status: "pending" | "active" | "complete" = "pending";
      if (currentStep === key) {
        status = "active";
      }
      const currentIndex = currentStep ? keys.indexOf(currentStep) : -1;
      const index = keys.indexOf(key);
      if (currentIndex > index) {
        status = "complete";
      }
      if (!currentStep && runtime?.progress && runtime.progress > 0) {
        status = "active";
      }
      return { key, label, status };
    });
  }, [runtime?.latestStep, runtime?.progress]);

  const videoSrc = activeProject?.sourceVideoPath
    ? convertFileSrc(activeProject.sourceVideoPath)
    : "";

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Button variant="text" onClick={() => navigate("/")}>
          Back
        </Button>
        <Box sx={{ flexGrow: 1 }}>
          <Tabs
            value={activeTabId ?? false}
            onChange={(_, value) => openProject(value)}
            variant="scrollable"
            scrollButtons="auto"
          >
            {openTabs.map((id) => (
              <Tab
                key={id}
                value={id}
                label={
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Typography variant="body2">
                      {projects[id]?.filename ?? "Workbench"}
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={(event) => {
                        event.stopPropagation();
                        closeProject(id);
                      }}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                }
              />
            ))}
          </Tabs>
        </Box>
      </Stack>
      {activeProject ? (
        <Box
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 2,
            overflow: "hidden"
          }}
        >
          <Stack direction="row" sx={{ minHeight: 480 }}>
            <Box
              sx={{
                width: leftOpen ? 260 : 0,
                borderRight: leftOpen ? "1px solid" : "none",
                borderColor: "divider",
                backgroundColor: "background.paper",
                display: leftOpen ? "flex" : "none",
                flexDirection: "column"
              }}
            >
              <Stack direction="row" alignItems="center" justifyContent="space-between" p={2}>
                <Typography variant="subtitle2">All subtitles</Typography>
                <Button size="small" variant="text" onClick={() => setLeftOpen(false)}>
                  Hide
                </Button>
              </Stack>
              <Divider />
              <Box sx={{ p: 2, color: "text.secondary" }}>Panel stub</Box>
            </Box>
            <Box sx={{ flex: 1, p: 3 }}>
              <Stack direction="row" justifyContent="flex-end" spacing={1} mb={2}>
                {!leftOpen ? (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => setLeftOpen(true)}
                    disabled={
                      workbenchState === "WB_NEEDS_VIDEO" ||
                      workbenchState === "WB_CREATING_SUBTITLES"
                    }
                  >
                    All subtitles
                  </Button>
                ) : null}
                {!rightOpen ? (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => setRightOpen(true)}
                    disabled={
                      workbenchState === "WB_NEEDS_VIDEO" ||
                      workbenchState === "WB_CREATING_SUBTITLES"
                    }
                  >
                    Style
                  </Button>
                ) : null}
              </Stack>
              {busyInOtherProject ? (
                <Box
                  sx={{
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 2,
                    p: 2,
                    mb: 2,
                    color: "text.secondary"
                  }}
                >
                  Busy — another project is running a long task.
                </Box>
              ) : null}
              {runtime?.cancelledAt ? (
                <Box
                  sx={{
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 2,
                    p: 2,
                    mb: 2,
                    color: "text.secondary"
                  }}
                >
                  Cancelled
                </Box>
              ) : null}
              {workbenchState === "WB_NEEDS_VIDEO" ? (
              <Stack spacing={2}>
                <Typography variant="h5">Choose video…</Typography>
                <Button variant="contained" onClick={handleRelink} disabled={actionsDisabled}>
                  Choose video…
                </Button>
              </Stack>
            ) : null}
              {workbenchState === "WB_VIDEO_LINKED_READY" ? (
                <Stack spacing={2}>
                  <Box
                    sx={{
                      borderRadius: 2,
                      overflow: "hidden",
                      border: "1px solid",
                      borderColor: "divider"
                    }}
                  >
                    <video src={videoSrc} controls style={{ width: "100%" }} />
                  </Box>
                  <Stack direction="row" spacing={2} alignItems="center">
                    <Button
                      variant="contained"
                      onClick={handleCreateSubtitles}
                      disabled={actionsDisabled}
                    >
                      Create subtitles
                    </Button>
                    <Typography color="text.secondary">
                      {formatDuration(activeProject.durationSeconds)}
                    </Typography>
                  </Stack>
                </Stack>
              ) : null}
              {workbenchState === "WB_CREATING_SUBTITLES" ? (
                <Stack spacing={2}>
                  <Typography variant="h5">Creating subtitles</Typography>
                  <Stack spacing={1}>
                    {steps.map((step) => (
                      <Stack
                        key={step.key}
                        direction="row"
                        spacing={1}
                        alignItems="center"
                      >
                        <Box
                          sx={{
                            width: 10,
                            height: 10,
                            borderRadius: "50%",
                            backgroundColor:
                              step.status === "complete"
                                ? "success.main"
                                : step.status === "active"
                                  ? "primary.main"
                                  : "text.disabled"
                          }}
                        />
                        <Typography color="text.secondary">{step.label}</Typography>
                      </Stack>
                    ))}
                  </Stack>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(100, Math.max(0, runtime?.progress ?? 0))}
                  />
                  <Typography color="text.secondary">Elapsed time: {elapsedSeconds}s</Typography>
                  <Button variant="outlined" onClick={handleCancel}>
                    Cancel
                  </Button>
                </Stack>
              ) : null}
              {workbenchState === "WB_SUBTITLES_READY" ? (
                <Stack spacing={2}>
                  <Typography variant="h5">Subtitles ready ✓</Typography>
                </Stack>
              ) : null}
              {workbenchState === "WB_EXPORTING" ? (
                <Stack spacing={2}>
                  <Typography variant="h5">Exporting video</Typography>
                </Stack>
              ) : null}
              {workbenchState === "WB_EXPORT_SUCCESS" ? (
                <Stack spacing={2}>
                  <Typography variant="h5">Subtitles ready ✓</Typography>
                </Stack>
              ) : null}
            </Box>
            <Box
              sx={{
                width: rightOpen ? 260 : 0,
                borderLeft: rightOpen ? "1px solid" : "none",
                borderColor: "divider",
                backgroundColor: "background.paper",
                display: rightOpen ? "flex" : "none",
                flexDirection: "column"
              }}
            >
              <Stack direction="row" alignItems="center" justifyContent="space-between" p={2}>
                <Typography variant="subtitle2">Style</Typography>
                <Button size="small" variant="text" onClick={() => setRightOpen(false)}>
                  Hide
                </Button>
              </Stack>
              <Divider />
              <Box sx={{ p: 2, color: "text.secondary" }}>Panel stub</Box>
            </Box>
          </Stack>
        </Box>
      ) : null}
      {(workbenchState === "WB_SUBTITLES_READY" || workbenchState === "WB_EXPORT_SUCCESS") &&
      activeProject ? (
        <Box
          sx={{
            position: "sticky",
            bottom: 0,
            borderRadius: 2,
            border: "1px solid",
            borderColor: "divider",
            backgroundColor: "background.paper",
            p: 2
          }}
        >
          <Button variant="contained" disabled={actionsDisabled}>
            Create video with subtitles
          </Button>
        </Box>
      ) : null}
      {runtime?.errorMessage ? (
        <Box
          sx={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center"
          }}
        >
          <Box
            sx={{
              width: 420,
              backgroundColor: "background.paper",
              borderRadius: 2,
              border: "1px solid",
              borderColor: "divider",
              p: 3
            }}
          >
            <Stack spacing={2}>
              <Typography variant="h6">{runtime.errorMessage}</Typography>
              {showDetails && runtime.errorDetails ? (
                <Typography color="text.secondary">{runtime.errorDetails}</Typography>
              ) : null}
              <Stack direction="row" spacing={2}>
                <Button
                  variant="contained"
                  onClick={() => {
                    if (activeProject) {
                      clearRuntimeError(activeProject.projectId);
                    }
                    setShowDetails(false);
                  }}
                >
                  Try again
                </Button>
                {runtime.errorDetails ? (
                  <Button
                    variant="outlined"
                    onClick={() => setShowDetails((prev) => !prev)}
                  >
                    Show details
                  </Button>
                ) : null}
              </Stack>
            </Stack>
          </Box>
        </Box>
      ) : null}
    </Stack>
  );
};

export default Workbench;
