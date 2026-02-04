import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  CardMedia,
  Chip,
  Stack,
  Typography
} from "@mui/material";
import { useCallback, useEffect, useMemo, useState } from "react";
import { convertFileSrc } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useNavigate } from "react-router-dom";
import { useProjects } from "../store/projectsContext";
import { pickVideoFile } from "../store/filePicker";
import { formatDuration } from "../store/utils";

const ProjectHub = () => {
  const navigate = useNavigate();
  const {
    projects,
    projectOrder,
    openProject,
    createProject,
    relinkProjectPath,
    refreshProjects
  } = useProjects();
  const [dragActive, setDragActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const supportedExtensions = [".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"];

  const isSupportedVideo = useCallback(
    (path: string) => {
      const lower = path.toLowerCase();
      return supportedExtensions.some((ext) => lower.endsWith(ext));
    },
    [supportedExtensions]
  );

  const normalizeSelection = (selection: string | string[] | null) => {
    if (!selection) {
      return null;
    }
    if (Array.isArray(selection)) {
      return selection[0] ?? null;
    }
    return selection;
  };

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    let unlistenDrop: (() => void) | undefined;
    let unlistenHover: (() => void) | undefined;
    let unlistenCancel: (() => void) | undefined;
    const listenEvents = async () => {
      unlistenDrop = await listen<string[]>("tauri://file-drop", (event) => {
        setDragActive(false);
        const [path] = event.payload ?? [];
        if (path) {
          void handleCreateProject(path);
        }
      });
      unlistenHover = await listen("tauri://file-drop-hover", () => {
        setDragActive(true);
      });
      unlistenCancel = await listen("tauri://file-drop-cancelled", () => {
        setDragActive(false);
      });
    };
    void listenEvents();
    return () => {
      unlistenDrop?.();
      unlistenHover?.();
      unlistenCancel?.();
    };
  }, [handleCreateProject]);

  const handleCreateProject = useCallback(
    async (path?: string) => {
      try {
        setErrorMessage(null);
        let sourcePath = path;
        if (!sourcePath) {
          const selection = await pickVideoFile();
          sourcePath = normalizeSelection(selection);
          if (!sourcePath) {
            return;
          }
        }
        if (!isSupportedVideo(sourcePath)) {
          setErrorMessage("Unsupported file type");
          return;
        }
        const result = await createProject(sourcePath);
        if (result.project) {
          setErrorMessage(null);
          openProject(result.project.projectId);
          navigate("/workbench");
        }
        if (result.metadataPromise) {
          result.metadataPromise.catch(() => {
            setErrorMessage("Failed to load video metadata.");
          });
        }
      } catch (error) {
        console.error(error);
        setErrorMessage("Failed to create project.");
      }
    },
    [createProject, isSupportedVideo, navigate, openProject]
  );

  const handleRelink = useCallback(
    async (projectId: string) => {
      setErrorMessage(null);
      const selection = await pickVideoFile();
      const sourcePath = normalizeSelection(selection);
      if (!sourcePath) {
        return;
      }
      if (!isSupportedVideo(sourcePath)) {
        setErrorMessage("Unsupported file type");
        return;
      }
      try {
        await relinkProjectPath(projectId, sourcePath);
      } catch (error) {
        console.error(error);
        setErrorMessage("Failed to relink project.");
      }
    },
    [isSupportedVideo, relinkProjectPath]
  );

  const cards = useMemo(
    () =>
      projectOrder.map((id) => {
        const project = projects[id];
        if (!project) {
          return null;
        }
        const isMissing = project.status === "Missing file";
        const thumbnail = project.thumbnailPath ? convertFileSrc(project.thumbnailPath) : "";
        return (
          <Card key={project.projectId} variant="outlined">
            <CardActionArea
              onClick={() => {
                if (isMissing) {
                  return;
                }
                openProject(project.projectId);
                navigate("/workbench");
              }}
              sx={{ height: "100%", opacity: isMissing ? 0.7 : 1 }}
            >
              {thumbnail ? (
                <CardMedia component="img" height="140" image={thumbnail} alt="" />
              ) : (
                <Box
                  sx={{
                    height: 140,
                    backgroundColor: "background.paper"
                  }}
                />
              )}
              <CardContent>
                <Stack spacing={1}>
                  <Typography variant="subtitle1" fontWeight={600} noWrap>
                    {project.filename}
                  </Typography>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Typography variant="body2" color="text.secondary">
                      {formatDuration(project.durationSeconds)}
                    </Typography>
                    <Chip
                      label={project.status}
                      size="small"
                      color={project.status === "Ready" ? "success" : "default"}
                      sx={{ borderRadius: "999px" }}
                    />
                  </Stack>
                  {isMissing ? (
                    <Box>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleRelink(project.projectId);
                        }}
                      >
                        Relink
                      </Button>
                    </Box>
                  ) : null}
                </Stack>
              </CardContent>
            </CardActionArea>
          </Card>
        );
      }),
    [handleRelink, navigate, openProject, projectOrder, projects]
  );

  return (
    <Stack spacing={3}>
      {errorMessage ? (
        <Box
          sx={{
            border: "1px solid",
            borderColor: "error.main",
            borderRadius: 2,
            p: 2,
            color: "error.main"
          }}
          role="alert"
        >
          <Typography>{errorMessage}</Typography>
        </Box>
      ) : null}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h4" fontWeight={600}>
          Project Hub
        </Typography>
        <Button variant="contained" onClick={() => void handleCreateProject()}>
          New project
        </Button>
      </Stack>
      <Box
        sx={{
          border: "1px dashed",
          borderColor: dragActive ? "primary.main" : "divider",
          borderRadius: 2,
          p: 3
        }}
      >
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
            gap: 2
          }}
        >
          {cards}
        </Box>
      </Box>
    </Stack>
  );
};

export default ProjectHub;
