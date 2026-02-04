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
import { getCurrentWindow } from "@tauri-apps/api/window";
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

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    const listen = async () => {
      unlisten = await getCurrentWindow().onDragDropEvent((event) => {
        if (event.payload.type === "over") {
          setDragActive(true);
        }
        if (event.payload.type === "drop") {
          setDragActive(false);
          const [path] = event.payload.paths;
          if (path) {
            void handleCreateProject(path);
          }
        }
        if (event.payload.type === "cancel") {
          setDragActive(false);
        }
      });
    };
    void listen();
    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, []);

  const handleCreateProject = useCallback(
    async (path?: string) => {
      let sourcePath = path;
      if (!sourcePath) {
        const selection = await pickVideoFile();
        if (!selection) {
          return;
        }
        sourcePath = selection;
      }
      const project = await createProject(sourcePath);
      if (project) {
        openProject(project.projectId);
        navigate("/workbench");
      }
    },
    [createProject, navigate, openProject]
  );

  const handleRelink = useCallback(
    async (projectId: string) => {
      const selection = await pickVideoFile();
      if (!selection) {
        return;
      }
      await relinkProjectPath(projectId, selection);
    },
    [relinkProjectPath]
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
