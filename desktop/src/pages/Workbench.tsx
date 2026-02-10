import * as React from "react";
import { ArrowLeft } from "lucide-react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import Checklist, { ChecklistItem } from "@/components/Checklist";
import StyleControls from "@/components/SubtitleStyle/StyleControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { buildGenerateChecklist, checklistStepIds } from "@/legacyCopy";
import { createSubtitlesJob, JobEvent, JobEventStream } from "@/jobsClient";
import {
  fetchProject,
  fetchProjectSubtitles,
  ProjectManifest,
  updateProject
} from "@/projectsClient";
import { useWindowWidth } from "@/hooks/useWindowWidth";
import { useWorkbenchTabs } from "@/workbenchTabs";
import { parseSrt, serializeSrt, SrtCue } from "@/lib/srt";
import {
  fetchSettings,
  SettingsConfig,
  SubtitleStyleAppearance,
  updateSettings
} from "@/settingsClient";

type WorkbenchLocationState = {
  autoStartSubtitles?: boolean;
} | null;

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

const extractErrorDetail = (message: string): string => {
  try {
    const parsed = JSON.parse(message) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    // ignore parse failures; return raw string below.
  }
  return message;
};

const DEFAULT_APPEARANCE: SubtitleStyleAppearance = {
  font_family: "Arial",
  font_size: 28,
  font_style: "regular",
  text_color: "#FFFFFF",
  text_opacity: 1.0,
  letter_spacing: 0,
  outline_enabled: true,
  outline_width: 2,
  outline_color: "#000000",
  shadow_enabled: true,
  shadow_strength: 1,
  shadow_offset_x: 0,
  shadow_offset_y: 0,
  shadow_color: "#000000",
  shadow_opacity: 1.0,
  background_mode: "none",
  line_bg_color: "#000000",
  line_bg_opacity: 0.7,
  line_bg_padding: 8,
  line_bg_radius: 0,
  word_bg_color: "#000000",
  word_bg_opacity: 0.4,
  word_bg_padding: 8,
  word_bg_radius: 0,
  vertical_anchor: "bottom",
  vertical_offset: 28,
  subtitle_mode: "word_highlight",
  highlight_color: "#FFD400"
};

const MISSING_SUBTITLES_REASON_TEXT: Record<string, string> = {
  no_speech_in_gaps: "no speech in the missing part",
  rescue_transcribe_empty: "could not recover any text",
  merge_rejected: "could not merge the fix",
  limits_reached: "hit a safety limit",
  rescue_error: "something went wrong"
};

const WORD_HIGHLIGHT_REASON_TEXT: Record<string, string> = {
  audio_missing: "audio missing",
  srt_missing: "subtitles file missing",
  align_process_failed: "could not sync to the audio",
  align_output_empty: "no timing data produced",
  align_output_invalid: "timing data was invalid"
};

const defaultChecklist = (items: { id: string; label: string }[]): ChecklistItem[] =>
  items.map((item) => ({ ...item, state: "pending" }));

const getPathSeparator = (value: string) => (value.includes("\\") ? "\\" : "/");

const getDirName = (value: string) => {
  const parts = value.split(/[/\\]/);
  parts.pop();
  return parts.join(getPathSeparator(value));
};

function useDebounce<T extends (...args: never[]) => void>(
  fn: T,
  delayMs: number
): T {
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const fnRef = React.useRef(fn);
  fnRef.current = fn;

  React.useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  return React.useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => {
        fnRef.current(...args);
      }, delayMs);
    },
    [delayMs]
  ) as T;
}

const Workbench = () => {
  const location = useLocation();
  const incomingState = location.state as WorkbenchLocationState;
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { tabs, ensureTab, updateTabMeta } = useWorkbenchTabs();
  const width = useWindowWidth();
  const isNarrow = width < 1100;
  const isTauriEnv = isTauri();
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const [project, setProject] = React.useState<ProjectManifest | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [subtitleLoadError, setSubtitleLoadError] = React.useState<string | null>(null);
  const [editError, setEditError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isStyleLoading, setIsStyleLoading] = React.useState(true);
  const [styleError, setStyleError] = React.useState<string | null>(null);
  const [settings, setSettings] = React.useState<SettingsConfig | null>(null);
  const [appearance, setAppearance] =
    React.useState<SubtitleStyleAppearance>(DEFAULT_APPEARANCE);
  const [preset, setPreset] = React.useState("Default");
  const [highlightOpacity, setHighlightOpacity] = React.useState(1.0);
  const [currentTimeSeconds, setCurrentTimeSeconds] = React.useState(0);
  const [cues, setCues] = React.useState<SrtCue[]>([]);
  const [selectedCueId, setSelectedCueId] = React.useState<string | null>(null);
  const [editingCueId, setEditingCueId] = React.useState<string | null>(null);
  const [editingText, setEditingText] = React.useState("");
  const [isSavingCue, setIsSavingCue] = React.useState(false);
  const [leftPanelOpen, setLeftPanelOpen] = React.useState(false);
  const [rightOverlayOpen, setRightOverlayOpen] = React.useState(false);
  const [isCreatingSubtitles, setIsCreatingSubtitles] = React.useState(false);
  const [createSubtitlesError, setCreateSubtitlesError] = React.useState<string | null>(null);
  const [createSubtitlesHeading, setCreateSubtitlesHeading] =
    React.useState("Creating subtitles");
  const [createSubtitlesProgressPct, setCreateSubtitlesProgressPct] = React.useState(0);
  const [createSubtitlesProgressMessage, setCreateSubtitlesProgressMessage] =
    React.useState<string>("");
  const [createSubtitlesChecklist, setCreateSubtitlesChecklist] = React.useState<ChecklistItem[]>(
    []
  );
  const [createSubtitlesJobStream, setCreateSubtitlesJobStream] =
    React.useState<JobEventStream | null>(null);
  const [projectReloadTick, setProjectReloadTick] = React.useState(0);
  const [subtitlesReloadTick, setSubtitlesReloadTick] = React.useState(0);
  const [pendingAutoStartSubtitles, setPendingAutoStartSubtitles] = React.useState(false);
  const handledAutoStartKeyRef = React.useRef<string | null>(null);
  const showSubtitlesOverlay = false;

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
  }, [projectId, projectReloadTick]);

  React.useEffect(() => {
    let active = true;
    if (!projectId) {
      setCues([]);
      setSelectedCueId(null);
      setEditingCueId(null);
      setEditingText("");
      setSubtitleLoadError(null);
      return () => {
        active = false;
      };
    }

    setCues([]);
    setSelectedCueId(null);
    setEditingCueId(null);
    setEditingText("");
    setSubtitleLoadError(null);
    fetchProjectSubtitles(projectId)
      .then((srtText) => {
        if (!active) return;
        setCues(parseSrt(srtText));
      })
      .catch((err) => {
        if (!active) return;
        const message =
          err instanceof Error ? extractErrorDetail(err.message) : "Failed to load subtitles.";
        if (message === "subtitles_not_found") {
          setSubtitleLoadError(null);
          return;
        }
        setSubtitleLoadError(message);
      });

    return () => {
      active = false;
    };
  }, [projectId, subtitlesReloadTick]);

  const applyStyleFromSettings = React.useCallback((data: SettingsConfig) => {
    const style = data.subtitle_style;
    const app = (style.appearance as SubtitleStyleAppearance | undefined) ?? DEFAULT_APPEARANCE;
    setAppearance({
      ...DEFAULT_APPEARANCE,
      ...app,
      subtitle_mode: data.subtitle_mode ?? app.subtitle_mode,
      highlight_color: style.highlight_color ?? app.highlight_color
    });
    setPreset(style.preset ?? "Default");
    setHighlightOpacity(style.highlight_opacity ?? 1.0);
  }, []);

  React.useEffect(() => {
    let active = true;
    setIsStyleLoading(true);
    fetchSettings()
      .then((data) => {
        if (!active) return;
        setSettings(data);
        applyStyleFromSettings(data);
        setStyleError(null);
      })
      .catch((err) => {
        if (!active) return;
        setStyleError(err instanceof Error ? err.message : "Failed to load style settings.");
      })
      .finally(() => {
        if (!active) return;
        setIsStyleLoading(false);
      });
    return () => {
      active = false;
    };
  }, [applyStyleFromSettings]);

  React.useEffect(() => {
    if (!projectId) {
      return;
    }
    ensureTab({ projectId, title: "Loading..." });
  }, [ensureTab, projectId]);

  React.useEffect(() => {
    if (!projectId) {
      return;
    }
    setLeftPanelOpen(false);
    setRightOverlayOpen(false);
    setCurrentTimeSeconds(0);
    setEditError(null);
    setCreateSubtitlesError(null);
    setCreateSubtitlesHeading("Creating subtitles");
    setCreateSubtitlesProgressPct(0);
    setCreateSubtitlesProgressMessage("");
    setCreateSubtitlesChecklist([]);
    setIsCreatingSubtitles(false);
    setCreateSubtitlesJobStream((prev) => {
      prev?.close();
      return null;
    });
  }, [projectId]);

  React.useEffect(() => {
    if (selectedCueId && !cues.some((cue) => cue.id === selectedCueId)) {
      setSelectedCueId(null);
    }
    if (editingCueId && !cues.some((cue) => cue.id === editingCueId)) {
      setEditingCueId(null);
      setEditingText("");
    }
  }, [cues, editingCueId, selectedCueId]);

  React.useEffect(() => {
    if (!projectId || !project) {
      return;
    }
    updateTabMeta(projectId, { title: resolveTitle(project) });
  }, [project, projectId, updateTabMeta]);

  React.useEffect(() => {
    if (!isNarrow) {
      setRightOverlayOpen(false);
    }
  }, [isNarrow]);

  React.useEffect(() => {
    return () => {
      createSubtitlesJobStream?.close();
    };
  }, [createSubtitlesJobStream]);

  React.useEffect(() => {
    if (!incomingState?.autoStartSubtitles) {
      return;
    }
    if (handledAutoStartKeyRef.current === location.key) {
      return;
    }
    handledAutoStartKeyRef.current = location.key;
    setPendingAutoStartSubtitles(true);
    window.history.replaceState({}, "");
  }, [incomingState, location.key]);

  const buildJobOptions = React.useCallback((config: SettingsConfig) => {
    return {
      quality: config.transcription_quality,
      apply_audio_filter: config.apply_audio_filter,
      keep_extracted_audio: config.keep_extracted_audio,
      punctuation_rescue_fallback_enabled: config.punctuation_rescue_fallback_enabled,
      vad_gap_rescue_enabled: true,
      subtitle_mode: config.subtitle_mode,
      highlight_color: config.subtitle_style?.highlight_color
    };
  }, []);

  const resolveOutputDir = React.useCallback(
    async (videoInputPath: string): Promise<string | null> => {
      if (!settings) {
        return null;
      }
      if (settings.save_policy === "same_folder") {
        return getDirName(videoInputPath);
      }
      if (settings.save_policy === "fixed_folder") {
        if (settings.save_folder) {
          return settings.save_folder;
        }
        setCreateSubtitlesError("Choose a folder in Settings to save your subtitles.");
        return null;
      }
      if (!isTauriEnv) {
        setCreateSubtitlesError("Choose a folder in Settings to save your subtitles.");
        return null;
      }
      const selected = await openDialog({ directory: true, multiple: false });
      if (typeof selected !== "string" || !selected) {
        return null;
      }
      return selected;
    },
    [isTauriEnv, settings]
  );

  const updateCreateChecklist = React.useCallback((stepId: string, stateValue: string, reason?: string) => {
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
    setCreateSubtitlesChecklist((prev) =>
      prev.map((item) =>
        item.id === stepId ? { ...item, state: mappedState, detail: reason ?? item.detail } : item
      )
    );
  }, []);

  const resolveChecklistReason = React.useCallback((event: JobEvent) => {
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
  }, []);

  const handleCreateSubtitlesEvent = React.useCallback(
    (event: JobEvent) => {
      if (event.type === "started") {
        setCreateSubtitlesHeading(event.heading ?? "Creating subtitles");
        return;
      }
      if (event.type === "checklist") {
        updateCreateChecklist(event.step_id, event.state, resolveChecklistReason(event));
        return;
      }
      if (event.type === "progress") {
        if (typeof event.pct === "number") {
          setCreateSubtitlesProgressPct(event.pct);
        }
        if (event.message) {
          setCreateSubtitlesProgressMessage(event.message);
        }
        return;
      }
      if (event.type === "completed") {
        setCreateSubtitlesProgressPct(100);
        setIsCreatingSubtitles(false);
        setCreateSubtitlesJobStream((prev) => {
          prev?.close();
          return null;
        });
        setProjectReloadTick((prev) => prev + 1);
        setSubtitlesReloadTick((prev) => prev + 1);
        return;
      }
      if (event.type === "cancelled") {
        setCreateSubtitlesProgressPct(0);
        setCreateSubtitlesProgressMessage("");
        setIsCreatingSubtitles(false);
        if (event.message) {
          setCreateSubtitlesError(event.message);
        }
        setCreateSubtitlesJobStream((prev) => {
          prev?.close();
          return null;
        });
        return;
      }
      if (event.type === "error") {
        setCreateSubtitlesProgressPct(0);
        setCreateSubtitlesProgressMessage("");
        setIsCreatingSubtitles(false);
        setCreateSubtitlesError(event.message ?? "Subtitle generation failed.");
        setCreateSubtitlesJobStream((prev) => {
          prev?.close();
          return null;
        });
      }
    },
    [resolveChecklistReason, updateCreateChecklist]
  );

  const startCreateSubtitles = React.useCallback(async () => {
    if (!projectId || !project?.video?.path || isCreatingSubtitles) {
      return;
    }
    if (!settings) {
      setCreateSubtitlesError("Settings are still loading. Please try again.");
      return;
    }

    const resolvedOutputDir = await resolveOutputDir(project.video.path);
    if (!resolvedOutputDir) {
      return;
    }

    setCreateSubtitlesError(null);
    setCreateSubtitlesHeading("Creating subtitles");
    setCreateSubtitlesProgressPct(0);
    setCreateSubtitlesProgressMessage("Starting...");
    setCreateSubtitlesChecklist(defaultChecklist(buildGenerateChecklist(settings)));
    setIsCreatingSubtitles(true);

    try {
      const job = await createSubtitlesJob(
        {
          inputPath: project.video.path,
          outputDir: resolvedOutputDir,
          projectId,
          options: buildJobOptions(settings)
        },
        {
          onEvent: handleCreateSubtitlesEvent,
          onError: () => {
            setIsCreatingSubtitles(false);
            setCreateSubtitlesError("Connection lost while streaming job updates.");
            setCreateSubtitlesJobStream((prev) => {
              prev?.close();
              return null;
            });
          }
        }
      );
      setCreateSubtitlesJobStream(job);
    } catch (err) {
      setIsCreatingSubtitles(false);
      setCreateSubtitlesError(
        err instanceof Error ? err.message : "Failed to start subtitle generation."
      );
    }
  }, [
    buildJobOptions,
    handleCreateSubtitlesEvent,
    isCreatingSubtitles,
    project,
    projectId,
    resolveOutputDir,
    settings
  ]);

  const cancelCreateSubtitles = React.useCallback(async () => {
    await createSubtitlesJobStream?.cancel();
  }, [createSubtitlesJobStream]);

  React.useEffect(() => {
    if (!pendingAutoStartSubtitles) {
      return;
    }
    if (isLoading || !project || !settings || isCreatingSubtitles) {
      return;
    }
    setPendingAutoStartSubtitles(false);
    if (cues.length > 0 || subtitleLoadError) {
      return;
    }
    void startCreateSubtitles();
  }, [
    cues.length,
    isCreatingSubtitles,
    isLoading,
    pendingAutoStartSubtitles,
    project,
    settings,
    startCreateSubtitles,
    subtitleLoadError
  ]);

  const title = resolveTitle(project);
  const statusLabel = resolveStatusLabel(project?.status);
  const videoPath = project?.video?.path ?? "";
  const previewSrc = videoPath ? (isTauriEnv ? convertFileSrc(videoPath) : videoPath) : "";
  const hasSubtitles = cues.length > 0;
  const showNoSubtitlesState = !isLoading && !error && !subtitleLoadError && !hasSubtitles;
  const hasVideoPreview = Boolean(previewSrc);
  const showLeftToggle = showSubtitlesOverlay && !leftPanelOpen;
  const isOverlayOpen = (showSubtitlesOverlay && leftPanelOpen) || rightOverlayOpen;
  const showScrim = hasSubtitles && isNarrow && isOverlayOpen;
  const activeCue = React.useMemo(() => {
    return (
      cues.find(
        (cue) => cue.startSeconds <= currentTimeSeconds && currentTimeSeconds <= cue.endSeconds
      ) ?? null
    );
  }, [cues, currentTimeSeconds]);
  const isEditingCue = editingCueId !== null;
  const isActiveCueSelected = activeCue ? selectedCueId === activeCue.id : false;
  const isEditingActiveCue = activeCue ? editingCueId === activeCue.id : false;

  React.useEffect(() => {
    if (hasSubtitles) {
      return;
    }
    setLeftPanelOpen(false);
    setRightOverlayOpen(false);
  }, [hasSubtitles]);

  const persistStyleSettings = React.useCallback(
    async (
      nextAppearance: SubtitleStyleAppearance,
      nextPreset: string,
      nextHighlightOpacity: number
    ) => {
      try {
        await updateSettings({
          subtitle_mode: nextAppearance.subtitle_mode,
          subtitle_style: {
            preset: nextPreset,
            highlight_color: nextAppearance.highlight_color,
            highlight_opacity: nextHighlightOpacity,
            appearance: nextAppearance as unknown as Record<string, unknown>
          }
        });
        setStyleError(null);
      } catch (err) {
        setStyleError(err instanceof Error ? err.message : "Failed to save style settings.");
      }
    },
    []
  );

  const debouncedPersistStyle = useDebounce(
    (
      nextAppearance: SubtitleStyleAppearance,
      nextPreset: string,
      nextHighlightOpacity: number
    ) => {
      void persistStyleSettings(nextAppearance, nextPreset, nextHighlightOpacity);
    },
    500
  );

  const handleAppearanceChange = (changes: Partial<SubtitleStyleAppearance>) => {
    setAppearance((prev) => {
      const next = { ...prev, ...changes };
      const nextPreset = preset === "Custom" ? preset : "Custom";
      debouncedPersistStyle(next, nextPreset, highlightOpacity);
      return next;
    });
    if (preset !== "Custom") {
      setPreset("Custom");
    }
  };

  const handlePresetChange = (nextPreset: string) => {
    setPreset(nextPreset);
    debouncedPersistStyle(appearance, nextPreset, highlightOpacity);
  };

  const handleHighlightOpacityChange = (nextHighlightOpacity: number) => {
    setHighlightOpacity(nextHighlightOpacity);
    debouncedPersistStyle(appearance, preset, nextHighlightOpacity);
  };

  const handleResetPreset = () => {
    void (async () => {
      await persistStyleSettings(appearance, preset, highlightOpacity);
      try {
        const data = await fetchSettings();
        applyStyleFromSettings(data);
        setStyleError(null);
      } catch (err) {
        setStyleError(err instanceof Error ? err.message : "Failed to reload style settings.");
      }
    })();
  };

  const handleCancelEdit = React.useCallback(() => {
    setEditingCueId(null);
    setEditingText("");
    setEditError(null);
  }, []);

  const handleSaveEdit = React.useCallback(async () => {
    if (!projectId || !editingCueId) {
      return;
    }
    const nextCues = cues.map((cue) =>
      cue.id === editingCueId
        ? {
            ...cue,
            text: editingText
          }
        : cue
    );

    setIsSavingCue(true);
    try {
      await updateProject(projectId, {
        subtitles_srt_text: serializeSrt(nextCues)
      });
      setCues(nextCues);
      setSelectedCueId(editingCueId);
      setEditingCueId(null);
      setEditingText("");
      setEditError(null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to save subtitle changes.");
    } finally {
      setIsSavingCue(false);
    }
  }, [cues, editingCueId, editingText, projectId]);

  const handleCueClick = React.useCallback(
    (cue: SrtCue) => {
      if (isSavingCue) {
        return;
      }
      setEditError(null);
      const videoElement = videoRef.current;
      const isPlaying = Boolean(videoElement && !videoElement.paused && !videoElement.ended);
      if (isPlaying) {
        videoElement?.pause();
        setSelectedCueId(cue.id);
        setEditingCueId(null);
        setEditingText(cue.text);
        return;
      }
      if (selectedCueId === cue.id) {
        setEditingCueId(cue.id);
        setEditingText(cue.text);
        return;
      }
      setSelectedCueId(cue.id);
      setEditingCueId(null);
      setEditingText(cue.text);
    },
    [isSavingCue, selectedCueId]
  );

  const openLeftPanel = () => {
    if (!showSubtitlesOverlay) {
      return;
    }
    if (isNarrow) {
      setRightOverlayOpen(false);
    }
    setLeftPanelOpen(true);
  };

  const closeLeftPanel = () => {
    setLeftPanelOpen(false);
  };

  const openRightOverlay = () => {
    if (!isNarrow) {
      return;
    }
    setLeftPanelOpen(false);
    setRightOverlayOpen(true);
  };

  const closeOverlays = React.useCallback(() => {
    if (showSubtitlesOverlay && leftPanelOpen) {
      setLeftPanelOpen(false);
    }
    if (rightOverlayOpen) {
      setRightOverlayOpen(false);
    }
  }, [leftPanelOpen, rightOverlayOpen, showSubtitlesOverlay]);

  React.useEffect(() => {
    if (!isOverlayOpen && !isEditingCue) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      if (isEditingCue) {
        event.preventDefault();
        handleCancelEdit();
        return;
      }
      closeOverlays();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeOverlays, handleCancelEdit, isEditingCue, isOverlayOpen]);

  const handleEditorKeyDown = async (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      handleCancelEdit();
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isSavingCue) {
        await handleSaveEdit();
      }
    }
  };

  const handleSelectTab = (targetId: string) => {
    if (targetId === projectId) {
      return;
    }
    navigate(`/workbench/${encodeURIComponent(targetId)}`);
  };

  const stylePanelContent = (
    <>
      {styleError && (
        <div
          className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive"
          data-testid="workbench-style-error"
        >
          {styleError}
        </div>
      )}
      {isStyleLoading ? (
        <p className="text-xs text-muted-foreground">Loading style controls...</p>
      ) : (
        <StyleControls
          appearance={appearance}
          preset={preset}
          highlightOpacity={highlightOpacity}
          onAppearanceChange={handleAppearanceChange}
          onPresetChange={handlePresetChange}
          onHighlightOpacityChange={handleHighlightOpacityChange}
          onResetPreset={handleResetPreset}
        />
      )}
    </>
  );

  return (
    <div data-testid="workbench" className="flex h-[calc(100vh-3rem)] flex-col gap-4">
      <div
        className="flex flex-wrap items-center gap-2 border-b border-border pb-2"
        role="tablist"
        aria-label="Open projects"
        data-testid="workbench-tabs"
      >
        {tabs.length === 0 ? (
          <span className="text-xs text-muted-foreground">No open projects</span>
        ) : (
          tabs.map((tab) => {
            const isActive = tab.projectId === projectId;
            const label = tab.title || "Untitled project";
            return (
              <div
                key={tab.projectId}
                className={cn(
                  "flex items-center rounded-md border px-2 py-1 text-sm",
                  isActive ? "border-primary/60 bg-accent/20" : "border-border bg-card"
                )}
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "max-w-[180px] truncate text-left text-sm",
                    isActive ? "text-foreground" : "text-muted-foreground"
                  )}
                  title={label}
                  data-testid={`workbench-tab-${tab.projectId}`}
                  onClick={() => handleSelectTab(tab.projectId)}
                >
                  {label}
                </button>
              </div>
            );
          })
        )}
      </div>
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

      {!isLoading && !error && showNoSubtitlesState && (
        <section
          className="flex flex-1 items-center justify-center rounded-lg border border-border bg-card p-6"
          data-testid="workbench-empty-state"
        >
          <div className="w-full max-w-xl space-y-4 text-center">
            {createSubtitlesError && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {createSubtitlesError}
              </div>
            )}

            {!isCreatingSubtitles ? (
              <>
                <p className="text-lg font-semibold text-foreground">No subtitles yet.</p>
                <Button
                  data-testid="workbench-create-subtitles"
                  onClick={() => void startCreateSubtitles()}
                >
                  Create subtitles
                </Button>
              </>
            ) : (
              <>
                <p className="text-lg font-semibold text-foreground">{createSubtitlesHeading}</p>
                {createSubtitlesChecklist.length > 0 && (
                  <Checklist items={createSubtitlesChecklist} className="text-left" />
                )}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{Math.round(createSubtitlesProgressPct)}%</span>
                    <span className="truncate">{createSubtitlesProgressMessage}</span>
                  </div>
                  <Progress value={createSubtitlesProgressPct} />
                </div>
                <div className="flex justify-center">
                  <Button
                    variant="secondary"
                    data-testid="workbench-cancel-create-subtitles"
                    onClick={() => void cancelCreateSubtitles()}
                  >
                    Cancel
                  </Button>
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {!isLoading && !error && !showNoSubtitlesState && (
        <>
          {hasSubtitles && ((showSubtitlesOverlay && showLeftToggle) || isNarrow) && (
            <div className="relative z-50 flex flex-wrap items-center gap-2">
              {showSubtitlesOverlay && showLeftToggle && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openLeftPanel}
                  data-testid="workbench-open-left"
                >
                  All subtitles
                </Button>
              )}
              {isNarrow && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={openRightOverlay}
                  data-testid="workbench-open-style"
                >
                  Style
                </Button>
              )}
            </div>
          )}

          <div className={cn("flex min-h-0 flex-1 gap-4", isNarrow ? "flex-col" : "flex-row")}>
            <section
              className="flex min-h-[220px] flex-1 items-center justify-center rounded-lg border border-border bg-muted p-4"
              data-testid="workbench-center-panel"
            >
              {hasVideoPreview ? (
                <div className="relative h-full w-full">
                  <video
                    ref={videoRef}
                    className="h-full w-full rounded-md bg-black object-contain"
                    controls
                    src={previewSrc}
                    onLoadedMetadata={(event) =>
                      setCurrentTimeSeconds(event.currentTarget.currentTime || 0)
                    }
                    onTimeUpdate={(event) =>
                      setCurrentTimeSeconds(event.currentTarget.currentTime || 0)
                    }
                    onSeeked={(event) => setCurrentTimeSeconds(event.currentTarget.currentTime || 0)}
                  />
                  {activeCue && (
                    <div className="pointer-events-none absolute inset-0 flex items-end justify-center px-4 pb-14">
                      {isEditingActiveCue ? (
                        <textarea
                          data-testid="workbench-subtitle-editor"
                          className="pointer-events-auto w-full max-w-[720px] resize-none rounded-md border border-primary/70 bg-background/95 px-3 py-2 text-center text-base leading-snug text-foreground shadow-lg outline-none"
                          value={editingText}
                          onChange={(event) => setEditingText(event.target.value)}
                          onKeyDown={handleEditorKeyDown}
                          rows={2}
                          autoFocus
                          disabled={isSavingCue}
                        />
                      ) : (
                        <button
                          type="button"
                          data-testid="workbench-active-subtitle"
                          className={cn(
                            "pointer-events-auto max-w-[720px] rounded-md px-3 py-2 text-center text-base font-medium leading-snug text-white shadow-lg transition",
                            isActiveCueSelected
                              ? "outline-2 outline-offset-2 outline-primary bg-black/55"
                              : "bg-black/45 hover:bg-black/60"
                          )}
                          onClick={() => handleCueClick(activeCue)}
                        >
                          {activeCue.text}
                        </button>
                      )}
                    </div>
                  )}
                  {subtitleLoadError && (
                    <div
                      className="pointer-events-none absolute left-3 top-3 rounded-md border border-destructive/50 bg-destructive/15 px-2 py-1 text-xs text-destructive"
                      data-testid="workbench-subtitles-error"
                    >
                      {subtitleLoadError}
                    </div>
                  )}
                  {editError && (
                    <div
                      className="pointer-events-none absolute right-3 top-3 rounded-md border border-destructive/50 bg-destructive/15 px-2 py-1 text-xs text-destructive"
                      data-testid="workbench-subtitle-save-error"
                    >
                      {editError}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">Preview not available</div>
              )}
            </section>

            {hasSubtitles && !isNarrow && (
              <section
                className="flex min-h-0 w-80 shrink-0 flex-col rounded-lg border border-border bg-card"
                data-testid="workbench-right-panel"
              >
                <div className="border-b border-border px-4 py-2">
                  <h2 className="text-sm font-semibold">Style</h2>
                </div>
                <ScrollArea className="min-h-0 flex-1 px-4 py-3">
                  {stylePanelContent}
                </ScrollArea>
              </section>
            )}
          </div>

          {showScrim && (
            <div
              className="fixed inset-0 z-40 bg-black/40"
              onClick={closeOverlays}
              data-testid="workbench-overlay-scrim"
            />
          )}

          {hasSubtitles && showSubtitlesOverlay && leftPanelOpen && (
            <aside
              className="fixed inset-y-0 left-0 z-50 flex w-[min(90vw,360px)] flex-col border-r border-border bg-card shadow-lg"
              data-testid="workbench-left-drawer"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2">
                <h2 className="text-sm font-semibold">All subtitles</h2>
                <Button variant="ghost" size="sm" onClick={closeLeftPanel}>
                  Close
                </Button>
              </div>
              <ScrollArea className="min-h-0 flex-1 px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  Placeholder — subtitles list will live here.
                </p>
              </ScrollArea>
            </aside>
          )}

          {hasSubtitles && isNarrow && rightOverlayOpen && (
            <aside
              className="fixed inset-y-0 right-0 z-50 flex w-[min(90vw,320px)] flex-col border-l border-border bg-card shadow-lg"
              data-testid="workbench-right-drawer"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2">
                <h2 className="text-sm font-semibold">Style</h2>
                <Button variant="ghost" size="sm" onClick={() => setRightOverlayOpen(false)}>
                  Close
                </Button>
              </div>
              <ScrollArea className="min-h-0 flex-1 px-4 py-3">
                {stylePanelContent}
              </ScrollArea>
            </aside>
          )}
        </>
      )}
    </div>
  );
};

export default Workbench;
