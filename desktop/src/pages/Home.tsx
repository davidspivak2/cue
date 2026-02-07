import * as React from "react";
import { CheckCircle2, ChevronDown, ChevronRight } from "lucide-react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { getCurrentWebview } from "@tauri-apps/api/webview";

import Checklist, { ChecklistItem } from "@/components/Checklist";
import DropZone from "@/components/DropZone";
import VideoCard from "@/components/VideoCard";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  buildExportChecklist,
  buildGenerateChecklist,
  checklistStepIds,
  legacyCopy
} from "@/legacyCopy";
import {
  createSubtitlesJob,
  createVideoWithSubtitlesJob,
  JobEvent,
  JobEventStream,
  JobKind
} from "@/jobsClient";
import { fetchSettings, SettingsConfig } from "@/settingsClient";
import { cn } from "@/lib/utils";

type AppState =
  | "EMPTY"
  | "VIDEO_SELECTED"
  | "WORKING"
  | "SUBTITLES_READY"
  | "EXPORT_DONE";

type LogEntry = {
  message: string;
  important?: boolean;
};

type FileWithPath = File & { path?: string };

const MISSING_SUBTITLES_REASON_TEXT: Record<string, string> = {
  no_speech_in_gaps: "no speech in the missing part",
  rescue_transcribe_empty: "couldn’t recover any text",
  merge_rejected: "couldn’t merge the fix",
  limits_reached: "hit a safety limit",
  rescue_error: "something went wrong"
};

const WORD_HIGHLIGHT_REASON_TEXT: Record<string, string> = {
  audio_missing: "audio missing",
  srt_missing: "subtitles file missing",
  align_process_failed: "couldn’t sync to the audio",
  align_output_empty: "no timing data produced",
  align_output_invalid: "timing data was invalid"
};

const getPathSeparator = (value: string) => (value.includes("\\") ? "\\" : "/");

const getDirName = (value: string) => {
  const parts = value.split(/[/\\]/);
  parts.pop();
  return parts.join(getPathSeparator(value));
};

const getStem = (value: string) => {
  const base = value.split(/[/\\]/).pop() ?? value;
  return base.replace(/\.[^/.]+$/, "");
};

const joinPath = (dir: string, file: string) => {
  const trimmed = dir.replace(/[\\\/]$/, "");
  return `${trimmed}${getPathSeparator(dir)}${file}`;
};

const formatElapsed = (elapsedSeconds: number) => {
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;
  return `${legacyCopy.progress.elapsedPrefix} ${String(minutes).padStart(2, "0")}:${String(
    seconds
  ).padStart(2, "0")}`;
};

const defaultChecklist = (items: { id: string; label: string }[]): ChecklistItem[] =>
  items.map((item) => ({ ...item, state: "pending" }));

const Home = () => {
  const [state, setState] = React.useState<AppState>("EMPTY");
  const [settings, setSettings] = React.useState<SettingsConfig | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [videoFile, setVideoFile] = React.useState<File | null>(null);
  const [videoPath, setVideoPath] = React.useState<string | null>(null);
  const [outputDir, setOutputDir] = React.useState<string | null>(null);
  const [srtPath, setSrtPath] = React.useState<string | null>(null);
  const [outputVideoPath, setOutputVideoPath] = React.useState<string | null>(null);
  const [previewFramePath, setPreviewFramePath] = React.useState<string | null>(null);
  const [logPath, setLogPath] = React.useState<string | null>(null);
  const [progressPct, setProgressPct] = React.useState<number>(0);
  const [progressMessage, setProgressMessage] = React.useState<string>("");
  const [statusHeading, setStatusHeading] = React.useState<string>("");
  const [elapsedText, setElapsedText] = React.useState<string>("");
  const [logs, setLogs] = React.useState<LogEntry[]>([]);
  const [checklistItems, setChecklistItems] = React.useState<ChecklistItem[]>([]);
  const [detailsOpen, setDetailsOpen] = React.useState(false);
  const [jobStream, setJobStream] = React.useState<JobEventStream | null>(null);

  const jobKindRef = React.useRef<JobKind | null>(null);
  const jobStartRef = React.useRef<number | null>(null);
  const previewUrlRef = React.useRef<string | null>(null);

  const isTauriEnv = isTauri();

  React.useEffect(() => {
    let active = true;
    fetchSettings()
      .then((data) => {
        if (active) {
          setSettings(data);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load settings.");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  React.useEffect(() => {
    if (state !== "WORKING" || jobStartRef.current === null) {
      setElapsedText("");
      return;
    }
    const interval = window.setInterval(() => {
      if (jobStartRef.current === null) {
        return;
      }
      const elapsedSeconds = Math.floor((Date.now() - jobStartRef.current) / 1000);
      setElapsedText(formatElapsed(elapsedSeconds));
    }, 500);
    return () => window.clearInterval(interval);
  }, [state]);

  React.useEffect(() => {
    return () => {
      jobStream?.close();
    };
  }, [jobStream]);

  React.useEffect(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    if (!videoFile) {
      return;
    }
    const url = URL.createObjectURL(videoFile);
    previewUrlRef.current = url;
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = null;
      }
    };
  }, [videoFile]);

  const resetJobState = React.useCallback(() => {
    setProgressPct(0);
    setProgressMessage("");
    setStatusHeading("");
    setElapsedText("");
    setLogs([]);
    setChecklistItems([]);
    setLogPath(null);
    jobKindRef.current = null;
    jobStartRef.current = null;
  }, []);

  const clearVideo = () => {
    setVideoFile(null);
    setVideoPath(null);
    setOutputDir(null);
    setSrtPath(null);
    setOutputVideoPath(null);
    setPreviewFramePath(null);
    setState("EMPTY");
    resetJobState();
  };

  const handleVideoPathSelected = React.useCallback(
    (path: string, file?: File | null) => {
      if (!path) {
        setError("Could not read this file path. Please try a different file.");
        return;
      }
      setError(null);
      setVideoFile(file ?? null);
      setVideoPath(path);
      setOutputDir(null);
      setSrtPath(null);
      setOutputVideoPath(null);
      setPreviewFramePath(null);
      resetJobState();
      setState("VIDEO_SELECTED");
    },
    [resetJobState]
  );

  const resolveVideoPath = (file: File) => {
    const withPath = file as FileWithPath;
    return withPath.path ?? "";
  };

  const handleVideoSelected = (file: File) => {
    const resolvedPath = resolveVideoPath(file);
    if (!resolvedPath) {
      setError("Could not read this file path. Please try a different file.");
      return;
    }
    handleVideoPathSelected(resolvedPath, file);
  };

  const chooseVideoPath = React.useCallback(async () => {
    if (!isTauriEnv) {
      return;
    }
    try {
      const selected = await openDialog({
        multiple: false,
        directory: false,
        filters: [
          {
            name: "Video files",
            extensions: ["mp4", "mkv", "mov", "m4v"]
          }
        ],
        pickerMode: "video"
      });
      if (typeof selected === "string" && selected) {
        handleVideoPathSelected(selected, null);
      }
    } catch (error) {
      setError("Could not open the file picker. Please try again.");
    }
  }, [handleVideoPathSelected, isTauriEnv]);

  React.useEffect(() => {
    if (!isTauriEnv) {
      return;
    }
    let unlisten: (() => void) | null = null;
    getCurrentWebview()
      .onDragDropEvent((event) => {
        const payload = event.payload;
        if (payload.type !== "drop") {
          return;
        }
        const [path] = payload.paths ?? [];
        if (path) {
          handleVideoPathSelected(path, null);
        }
      })
      .then((stop) => {
        unlisten = stop;
      })
      .catch(() => {});
    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, [handleVideoPathSelected, isTauriEnv]);

  const resolveOutputDir = async (): Promise<string | null> => {
    if (!videoPath || !settings) {
      return null;
    }
    if (settings.save_policy === "same_folder") {
      return getDirName(videoPath);
    }
    if (settings.save_policy === "fixed_folder") {
      if (settings.save_folder) {
        return settings.save_folder;
      }
      setError("Choose a folder in Settings to save your subtitles.");
      return null;
    }
    const selected = await openDialog({ directory: true, multiple: false });
    if (typeof selected !== "string" || !selected) {
      return null;
    }
    return selected;
  };

  const buildJobOptions = (config: SettingsConfig) => ({
    quality: config.transcription_quality,
    apply_audio_filter: config.apply_audio_filter,
    keep_extracted_audio: config.keep_extracted_audio,
    punctuation_rescue_fallback_enabled: config.punctuation_rescue_fallback_enabled,
    vad_gap_rescue_enabled: true,
    subtitle_mode: config.subtitle_mode,
    highlight_color: config.subtitle_style?.highlight_color
  });

  const updateChecklist = (stepId: string, stateValue: string, reason?: string) => {
    const mappedState =
      stateValue === "start"
        ? "active"
        : stateValue === "done"
          ? "done"
          : stateValue === "skipped"
            ? "skipped"
            : stateValue === "failed"
              ? "failed"
              : "pending";
    setChecklistItems((prev) =>
      prev.map((item) =>
        item.id === stepId ? { ...item, state: mappedState, detail: reason ?? item.detail } : item
      )
    );
  };

  const resolveChecklistReason = (event: JobEvent) => {
    if (event.type !== "checklist") {
      return undefined;
    }
    if (event.reason_text) {
      return event.reason_text;
    }
    if (event.step_id === checklistStepIds.fixMissingSubtitles && event.reason_code) {
      return MISSING_SUBTITLES_REASON_TEXT[event.reason_code];
    }
    if (event.step_id === checklistStepIds.timingWordHighlights && event.reason_code) {
      return WORD_HIGHLIGHT_REASON_TEXT[event.reason_code];
    }
    return undefined;
  };

  const handleJobEvent = (event: JobEvent) => {
    if (event.type === "started") {
      jobStartRef.current = Date.now();
      setElapsedText(formatElapsed(0));
      setStatusHeading(
        event.heading ??
          (jobKindRef.current === "create_video_with_subtitles"
            ? legacyCopy.working.createVideoHeading
            : legacyCopy.working.createSubtitlesHeading)
      );
      setState("WORKING");
      if (event.log_path) {
        setLogPath(event.log_path);
      }
      return;
    }
    if (event.type === "checklist") {
      updateChecklist(event.step_id, event.state, resolveChecklistReason(event));
      return;
    }
    if (event.type === "progress") {
      if (typeof event.pct === "number") {
        setProgressPct(event.pct);
      }
      if (event.message) {
        setProgressMessage(event.message);
      }
      return;
    }
    if (event.type === "log") {
      setLogs((prev) => [...prev, { message: event.message, important: event.important }]);
      return;
    }
    if (event.type === "result") {
      const payload = event.payload ?? {};
      const payloadLog = payload.log_path;
      if (typeof payloadLog === "string") {
        setLogPath(payloadLog);
      }
      if (typeof payload.srt_path === "string") {
        setSrtPath(payload.srt_path);
      }
      if (typeof payload.output_path === "string") {
        setOutputVideoPath(payload.output_path);
      }
      if (typeof payload.preview_frame_path === "string") {
        setPreviewFramePath(payload.preview_frame_path);
      }
      if (jobKindRef.current === "create_subtitles") {
        updateChecklist(checklistStepIds.preparingPreview, "done");
      }
      return;
    }
    if (event.type === "completed") {
      setProgressPct(100);
      setProgressMessage("");
      jobStartRef.current = null;
      if (jobKindRef.current === "create_video_with_subtitles") {
        setState("EXPORT_DONE");
      } else {
        setState("SUBTITLES_READY");
      }
      return;
    }
    if (event.type === "cancelled") {
      setProgressPct(0);
      setProgressMessage("");
      jobStartRef.current = null;
      setState(videoPath ? "VIDEO_SELECTED" : "EMPTY");
      if (event.message) {
        setError(event.message);
      }
      return;
    }
    if (event.type === "error") {
      setProgressPct(0);
      setProgressMessage("");
      jobStartRef.current = null;
      setState(videoPath ? "VIDEO_SELECTED" : "EMPTY");
      setError(event.message ?? "Job failed.");
    }
  };

  const startSubtitlesJob = async () => {
    if (!videoPath || !settings) {
      return;
    }
    const resolvedOutputDir = await resolveOutputDir();
    if (!resolvedOutputDir) {
      return;
    }
    setOutputDir(resolvedOutputDir);
    setError(null);
    resetJobState();
    setChecklistItems(defaultChecklist(buildGenerateChecklist(settings)));
    jobKindRef.current = "create_subtitles";
    setState("WORKING");
    setStatusHeading(legacyCopy.working.createSubtitlesHeading);
    setProgressMessage("Starting...");
    const job = await createSubtitlesJob(
      {
        inputPath: videoPath,
        outputDir: resolvedOutputDir,
        options: buildJobOptions(settings)
      },
      {
        onEvent: handleJobEvent,
        onError: () => setError("Connection lost while streaming job updates.")
      }
    );
    setJobStream(job);
  };

  const startExportJob = async () => {
    if (!videoPath || !settings) {
      return;
    }
    if (!srtPath) {
      setError("Create subtitles first.");
      return;
    }
    const resolvedOutputDir = outputDir ?? (await resolveOutputDir());
    if (!resolvedOutputDir) {
      return;
    }
    setOutputDir(resolvedOutputDir);
    setError(null);
    resetJobState();
    setChecklistItems(defaultChecklist(buildExportChecklist()));
    jobKindRef.current = "create_video_with_subtitles";
    const job = await createVideoWithSubtitlesJob(
      {
        inputPath: videoPath,
        outputDir: resolvedOutputDir,
        srtPath,
        options: buildJobOptions(settings)
      },
      {
        onEvent: handleJobEvent,
        onError: () => setError("Connection lost while streaming job updates.")
      }
    );
    setJobStream(job);
  };

  const cancelJob = async () => {
    await jobStream?.cancel();
  };

  const openDetailsFile = async () => {
    if (logPath) {
      await openPath(logPath);
    }
  };

  const openOutputVideo = async () => {
    if (outputVideoPath) {
      await openPath(outputVideoPath);
    }
  };

  const openOutputFolder = async () => {
    const folder = outputVideoPath ? getDirName(outputVideoPath) : outputDir;
    if (folder) {
      await openPath(folder);
    }
  };

  const editSubtitlesAgain = async () => {
    if (srtPath) {
      await openPath(srtPath);
    }
  };

  const framePreviewUrl = previewFramePath ? convertFileSrc(previewFramePath) : null;
  const filePreviewUrl = previewUrlRef.current ?? null;
  const pathPreviewUrl =
    !framePreviewUrl && !filePreviewUrl && isTauriEnv && videoPath
      ? convertFileSrc(videoPath)
      : null;
  const videoCardPreviewUrl = framePreviewUrl ?? filePreviewUrl ?? pathPreviewUrl;
  const videoCardPreviewKind =
    framePreviewUrl || filePreviewUrl ? "image" : pathPreviewUrl ? "video" : "image";
  const savingAsPath =
    outputVideoPath ||
    (outputDir && videoPath
      ? joinPath(outputDir, `${getStem(videoPath)}_subtitled.mp4`)
      : "");

  const isWorking = state === "WORKING";
  const fileSelectedHandler = isTauriEnv ? undefined : handleVideoSelected;
  const choosePathHandler = isTauriEnv ? chooseVideoPath : undefined;

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {state === "EMPTY" && (
        <DropZone
          onFileSelected={fileSelectedHandler}
          onChoosePath={choosePathHandler}
          disabled={isWorking}
        />
      )}

      {state === "VIDEO_SELECTED" && (
        <div className="space-y-4">
          <VideoCard
            fileName={videoPath ? getStem(videoPath) : undefined}
            thumbnailUrl={videoCardPreviewUrl ?? undefined}
            previewKind={videoCardPreviewKind}
            onClear={clearVideo}
            onFileSelected={fileSelectedHandler}
            onChoosePath={choosePathHandler}
            disabled={isWorking}
          />
          <Button onClick={startSubtitlesJob} disabled={isWorking}>
            {legacyCopy.videoSelected.cta}
          </Button>
        </div>
      )}

      {state === "WORKING" && (
        <div className="space-y-4">
          <div className="text-center">
            <h2 className="text-xl font-semibold text-foreground">{statusHeading}</h2>
            {progressMessage && (
              <p className="text-sm text-muted-foreground">{progressMessage}</p>
            )}
          </div>
          {checklistItems.length > 0 && <Checklist items={checklistItems} />}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{Math.round(progressPct)}%</span>
              <span>{elapsedText}</span>
            </div>
            <Progress value={progressPct} />
          </div>
          <div className="flex justify-center">
            <Button variant="secondary" onClick={cancelJob}>
              {legacyCopy.working.cancel}
            </Button>
          </div>
        </div>
      )}

      {state === "SUBTITLES_READY" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-xl font-semibold">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            {legacyCopy.subtitlesReady.header}
          </div>
          <div
            className={cn(
              "overflow-hidden rounded-lg border border-border bg-muted",
              framePreviewUrl ? "" : "flex items-center justify-center"
            )}
            style={{ aspectRatio: "16 / 9" }}
          >
            {framePreviewUrl ? (
              <img src={framePreviewUrl} alt="Preview" className="h-full w-full object-cover" />
            ) : (
              <div className="text-sm text-muted-foreground">
                {legacyCopy.videoCard.placeholder}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">
              {legacyCopy.subtitlesReady.footerPrefix}
            </span>
            <span className="truncate">{savingAsPath}</span>
          </div>
          <Button onClick={startExportJob}>{legacyCopy.subtitlesReady.cta}</Button>
        </div>
      )}

      {state === "EXPORT_DONE" && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">{legacyCopy.done.header}</h2>
          <div className="flex flex-wrap gap-2">
            <Button onClick={openOutputVideo}>{legacyCopy.done.playVideo}</Button>
            <Button variant="secondary" onClick={openOutputFolder}>
              {legacyCopy.done.openFolder}
            </Button>
            <Button variant="ghost" onClick={editSubtitlesAgain}>
              {legacyCopy.done.editSubtitles}
            </Button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <button
          type="button"
          className="flex items-center gap-2 text-sm font-medium text-foreground"
          onClick={() => setDetailsOpen((prev) => !prev)}
        >
          {detailsOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          {detailsOpen ? "Hide details" : legacyCopy.details.toggle}
        </button>
        {detailsOpen && (
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">{legacyCopy.details.groupTitle}</h3>
              <Button
                variant="secondary"
                size="sm"
                onClick={openDetailsFile}
                disabled={!logPath}
              >
                {legacyCopy.details.openFile}
              </Button>
            </div>
            <div className="mt-3 max-h-60 space-y-2 overflow-y-auto text-sm text-muted-foreground">
              {logs.length === 0 && <p>No details yet.</p>}
              {logs.map((entry, index) => (
                <p
                  key={`${entry.message}-${index}`}
                  className={entry.important ? "text-foreground" : undefined}
                >
                  {entry.message}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Home;