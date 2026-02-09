import * as React from "react";
import { ArrowLeft } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchProject, ProjectManifest } from "@/projectsClient";

const STATUS_LABELS: Record<string, string> = {
  needs_video: "Needs video",
  needs_subtitles: "Needs subtitles",
  ready: "Ready",
  exporting: "Exporting",
  done: "Done",
  missing_file: "Missing file"
};

const getFileName = (value?: string | null) => {
  if (!value) {
    return "Untitled project";
  }
  const parts = value.split(/[/\\]/);
  return parts[parts.length - 1] ?? value;
};

const resolveTitle = (project: ProjectManifest | null) => {
  const filename = project?.video?.filename ?? project?.video?.path ?? "";
  return filename ? getFileName(filename) : "Untitled project";
};

const resolveStatusLabel = (status?: string | null) => {
  if (!status) {
    return "Loading";
  }
  return STATUS_LABELS[status] ?? "Needs subtitles";
};

const Workbench = () => {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const [project, setProject] = React.useState<ProjectManifest | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  React.useEffect(() => {
    let active = true;
    if (!projectId) {
      setError("Missing project id.");
      setIsLoading(false);
      return () => {
        active = false;
      };
    }
    setIsLoading(true);
    fetchProject(projectId)
      .then((data) => {
        if (!active) return;
        setProject(data);
        setError(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load project.");
      })
      .finally(() => {
        if (!active) return;
        setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  const title = resolveTitle(project);
  const statusLabel = resolveStatusLabel(project?.status);

  return (
    <div data-testid="workbench" className="flex h-[calc(100vh-3rem)] flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="gap-2"
          onClick={() => navigate("/")}
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <div className="min-w-0 text-center">
          <h1 className="text-lg font-semibold">Workbench</h1>
          <p className="truncate text-sm text-muted-foreground">{title}</p>
        </div>
        <Badge variant="secondary">{statusLabel}</Badge>
      </header>

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Loading project…
        </div>
      )}

      {!isLoading && error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!isLoading && !error && (
        <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row">
          <section className="rounded-lg border border-border bg-card p-4 lg:w-72 lg:shrink-0">
            <h2 className="text-sm font-semibold">All subtitles</h2>
            <p className="mt-2 text-xs text-muted-foreground">
              Placeholder — subtitles list will live here.
            </p>
          </section>

          <section className="flex min-h-[220px] flex-1 items-center justify-center rounded-lg border border-border bg-muted p-4">
            <div className="text-sm text-muted-foreground">Video preview placeholder</div>
          </section>

          <section className="rounded-lg border border-border bg-card p-4 lg:w-80 lg:shrink-0">
            <h2 className="text-sm font-semibold">Style</h2>
            <p className="mt-2 text-xs text-muted-foreground">
              Placeholder — style controls will live here.
            </p>
          </section>
        </div>
      )}
    </div>
  );
};

export default Workbench;
