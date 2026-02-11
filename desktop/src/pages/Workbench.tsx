import * as React from "react";
import { ArrowLeft, Check, RotateCcw, X } from "lucide-react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import Checklist, { ChecklistItem } from "@/components/Checklist";
import StyleControls from "@/components/SubtitleStyle/StyleControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import {
  buildExportChecklist,
  buildGenerateChecklist,
  checklistStepIds
} from "@/legacyCopy";
import {
  createSubtitlesJob,
  createVideoWithSubtitlesJob,
  JobEvent,
  JobEventStream
} from "@/jobsClient";
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
  SubtitleStyleAppearance
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

type PresetStyleDefaults = {
  font_size: number;
  outline: number;
  shadow: number;
  margin_v: number;
  box_enabled: boolean;
  box_opacity: number;
  box_padding: number;
};

const PRESET_STYLE_DEFAULTS: Record<"Default" | "Large outline" | "Large outline + box", PresetStyleDefaults> =
  {
    Default: {
      font_size: 34,
      outline: 1.5,
      shadow: 1,
      margin_v: 28,
      box_enabled: false,
      box_opacity: 55,
      box_padding: 8
    },
    "Large outline": {
      font_size: 38,
      outline: 2,
      shadow: 1,
      margin_v: 30,
      box_enabled: false,
      box_opacity: 55,
      box_padding: 9
    },
    "Large outline + box": {
      font_size: 38,
      outline: 2,
      shadow: 1,
      margin_v: 30,
      box_enabled: true,
      box_opacity: 55,
      box_padding: 9
    }
  };

const applyPresetAppearance = (
  source: SubtitleStyleAppearance,
  presetName: string
): SubtitleStyleAppearance => {
  if (presetName === "Custom") {
    return source;
  }
  const defaults =
    presetName === "Large outline" || presetName === "Large outline + box"
      ? PRESET_STYLE_DEFAULTS[presetName]
      : PRESET_STYLE_DEFAULTS.Default;
  return {
    ...source,
    font_family: DEFAULT_APPEARANCE.font_family,
    font_size: defaults.font_size,
    font_style: "regular",
    text_color: DEFAULT_APPEARANCE.text_color,
    text_opacity: 1,
    letter_spacing: 0,
    outline_enabled: defaults.outline > 0,
    outline_width: defaults.outline,
    outline_color: DEFAULT_APPEARANCE.outline_color,
    shadow_enabled: defaults.shadow > 0,
    shadow_strength: defaults.shadow,
    shadow_offset_x: 0,
    shadow_offset_y: 0,
    shadow_color: DEFAULT_APPEARANCE.shadow_color,
    shadow_opacity: 1,
    background_mode: defaults.box_enabled ? "line" : "none",
    line_bg_color: DEFAULT_APPEARANCE.line_bg_color,
    line_bg_opacity: defaults.box_opacity / 100,
    line_bg_padding: defaults.box_padding,
    line_bg_radius: 0,
    word_bg_color: DEFAULT_APPEARANCE.word_bg_color,
    word_bg_opacity: DEFAULT_APPEARANCE.word_bg_opacity,
    word_bg_padding: defaults.box_padding,
    word_bg_radius: 0,
    vertical_anchor: "bottom",
    vertical_offset: defaults.margin_v
  };
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

const EDIT_UNDO_COALESCE_MS = 600;
const HEX_COLOR_PATTERN = /^#[0-9a-f]{6}$/i;
const RTL_CHAR_PATTERN = /[\u0590-\u08FF]/;

const defaultChecklist = (items: { id: string; label: string }[]): ChecklistItem[] =>
  items.map((item) => ({ ...item, state: "pending" }));

const clampOpacity = (value: number) => Math.max(0, Math.min(1, value));

const colorWithOpacity = (hex: string, opacity: number) => {
  if (!HEX_COLOR_PATTERN.test(hex)) {
    return hex;
  }
  const red = Number.parseInt(hex.slice(1, 3), 16);
  const green = Number.parseInt(hex.slice(3, 5), 16);
  const blue = Number.parseInt(hex.slice(5, 7), 16);
  return `rgba(${red}, ${green}, ${blue}, ${clampOpacity(opacity)})`;
};

const buildOutlineShadows = (color: string, width: number) => {
  const radius = Math.max(0, Math.round(width));
  if (radius <= 0) {
    return [] as string[];
  }
  const shadows: string[] = [];
  for (let x = -radius; x <= radius; x += 1) {
    for (let y = -radius; y <= radius; y += 1) {
      if (x === 0 && y === 0) {
        continue;
      }
      if (x * x + y * y <= radius * radius) {
        shadows.push(`${x}px ${y}px 0 ${color}`);
      }
    }
  }
  return shadows;
};

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
  const activeSubtitleRef = React.useRef<HTMLTextAreaElement | null>(null);
  const shouldResumePlaybackRef = React.useRef(false);
  const editHistoryRef = React.useRef<string[]>([]);
  const editHistoryIndexRef = React.useRef(0);
  const lastHistoryCommitAtRef = React.useRef(0);
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
  const customAppearanceRef = React.useRef<SubtitleStyleAppearance>(DEFAULT_APPEARANCE);
  const [preset, setPreset] = React.useState("Default");
  const [highlightOpacity, setHighlightOpacity] = React.useState(1.0);
  const [currentTimeSeconds, setCurrentTimeSeconds] = React.useState(0);
  const [cues, setCues] = React.useState<SrtCue[]>([]);
  const [selectedCueId, setSelectedCueId] = React.useState<string | null>(null);
  const [editingCueId, setEditingCueId] = React.useState<string | null>(null);
  const [editingText, setEditingText] = React.useState("");
  const [canUndoEdit, setCanUndoEdit] = React.useState(false);
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
  const [isExporting, setIsExporting] = React.useState(false);
  const [exportError, setExportError] = React.useState<string | null>(null);
  const [exportHeading, setExportHeading] = React.useState("Exporting video");
  const [exportProgressPct, setExportProgressPct] = React.useState(0);
  const [exportProgressMessage, setExportProgressMessage] = React.useState<string>("");
  const [exportChecklist, setExportChecklist] = React.useState<ChecklistItem[]>([]);
  const [exportJobStream, setExportJobStream] = React.useState<JobEventStream | null>(null);
  const [exportOutputPath, setExportOutputPath] = React.useState<string | null>(null);
  const [projectReloadTick, setProjectReloadTick] = React.useState(0);
  const [subtitlesReloadTick, setSubtitlesReloadTick] = React.useState(0);
  const [pendingAutoStartSubtitles, setPendingAutoStartSubtitles] = React.useState(false);
  const handledAutoStartKeyRef = React.useRef<string | null>(null);
  const styleBootstrapKeyRef = React.useRef<string | null>(null);
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
        setExportOutputPath(data.latest_export?.output_video_path ?? null);
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
      setCanUndoEdit(false);
      editHistoryRef.current = [];
      editHistoryIndexRef.current = 0;
      lastHistoryCommitAtRef.current = 0;
      shouldResumePlaybackRef.current = false;
      setSubtitleLoadError(null);
      return () => {
        active = false;
      };
    }

    setCues([]);
    setSelectedCueId(null);
    setEditingCueId(null);
    setEditingText("");
    setCanUndoEdit(false);
    editHistoryRef.current = [];
    editHistoryIndexRef.current = 0;
    lastHistoryCommitAtRef.current = 0;
    shouldResumePlaybackRef.current = false;
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
    const resolvedAppearance = {
      ...DEFAULT_APPEARANCE,
      ...app,
      subtitle_mode: data.subtitle_mode ?? app.subtitle_mode,
      highlight_color: style.highlight_color ?? app.highlight_color
    };
    const resolvedPreset = style.preset ?? "Default";
    setAppearance(resolvedAppearance);
    setPreset(resolvedPreset);
    if (resolvedPreset === "Custom") {
      customAppearanceRef.current = resolvedAppearance;
    }
    setHighlightOpacity(style.highlight_opacity ?? 1.0);
  }, []);

  const applyStyleFromProject = React.useCallback((rawStyle: unknown): boolean => {
    if (!rawStyle || typeof rawStyle !== "object") {
      return false;
    }
    const root = rawStyle as Record<string, unknown>;
    if (Object.keys(root).length === 0) {
      return false;
    }
    const styleSection =
      root.subtitle_style && typeof root.subtitle_style === "object"
        ? (root.subtitle_style as Record<string, unknown>)
        : root;
    const rawAppearance =
      styleSection.appearance && typeof styleSection.appearance === "object"
        ? (styleSection.appearance as Record<string, unknown>)
        : styleSection;
    if (!rawAppearance || Object.keys(rawAppearance).length === 0) {
      return false;
    }

    const styleMode =
      typeof root.subtitle_mode === "string"
        ? root.subtitle_mode
        : typeof rawAppearance.subtitle_mode === "string"
          ? rawAppearance.subtitle_mode
          : undefined;
    const highlightColor =
      typeof styleSection.highlight_color === "string"
        ? styleSection.highlight_color
        : typeof root.highlight_color === "string"
          ? root.highlight_color
          : typeof rawAppearance.highlight_color === "string"
            ? rawAppearance.highlight_color
            : undefined;
    const resolvedAppearance = {
      ...DEFAULT_APPEARANCE,
      ...(rawAppearance as unknown as SubtitleStyleAppearance),
      subtitle_mode: styleMode ?? DEFAULT_APPEARANCE.subtitle_mode,
      highlight_color: highlightColor ?? DEFAULT_APPEARANCE.highlight_color
    };
    const resolvedPreset =
      typeof styleSection.preset === "string" ? styleSection.preset : "Default";
    const resolvedOpacity =
      typeof styleSection.highlight_opacity === "number"
        ? styleSection.highlight_opacity
        : 1.0;
    setAppearance(resolvedAppearance);
    setPreset(resolvedPreset);
    if (resolvedPreset === "Custom") {
      customAppearanceRef.current = resolvedAppearance;
    }
    setHighlightOpacity(resolvedOpacity);
    return true;
  }, []);

  const buildProjectStylePayload = React.useCallback(
    (
      nextAppearance: SubtitleStyleAppearance,
      nextPreset: string,
      nextHighlightOpacity: number
    ) => ({
      subtitle_mode: nextAppearance.subtitle_mode,
      subtitle_style: {
        preset: nextPreset,
        highlight_color: nextAppearance.highlight_color,
        highlight_opacity: nextHighlightOpacity,
        appearance: nextAppearance as unknown as Record<string, unknown>
      }
    }),
    []
  );

  React.useEffect(() => {
    let active = true;
    setIsStyleLoading(true);
    fetchSettings()
      .then((data) => {
        if (!active) return;
        setSettings(data);
        setStyleError(null);
      })
      .catch((err) => {
        if (!active) return;
        setStyleError(err instanceof Error ? err.message : "Failed to load style settings.");
        setIsStyleLoading(false);
      })
      .finally(() => {
        if (!active) return;
        if (!projectId) {
          setIsStyleLoading(false);
        }
      })
    return () => {
      active = false;
    };
  }, [projectId]);

  React.useEffect(() => {
    if (!projectId || !project || !settings) {
      return;
    }
    const bootstrapKey = `${projectId}:${project.updated_at}`;
    if (styleBootstrapKeyRef.current === bootstrapKey) {
      return;
    }
    styleBootstrapKeyRef.current = bootstrapKey;
    setIsStyleLoading(true);
    const appliedProjectStyle = applyStyleFromProject(project.style);
    if (appliedProjectStyle) {
      setStyleError(null);
      setIsStyleLoading(false);
      return;
    }

    applyStyleFromSettings(settings);
    const fallbackPayload = buildProjectStylePayload(
      {
        ...DEFAULT_APPEARANCE,
        ...(settings.subtitle_style?.appearance as SubtitleStyleAppearance | undefined),
        subtitle_mode: settings.subtitle_mode ?? DEFAULT_APPEARANCE.subtitle_mode,
        highlight_color:
          settings.subtitle_style?.highlight_color ?? DEFAULT_APPEARANCE.highlight_color
      },
      settings.subtitle_style?.preset ?? "Default",
      settings.subtitle_style?.highlight_opacity ?? 1.0
    );
    void updateProject(projectId, { style: fallbackPayload })
      .then(() => {
        setStyleError(null);
        setProjectReloadTick((prev) => prev + 1);
      })
      .catch((err) => {
        setStyleError(
          err instanceof Error ? err.message : "Failed to save project style settings."
        );
      })
      .finally(() => {
        setIsStyleLoading(false);
      });
  }, [
    applyStyleFromProject,
    applyStyleFromSettings,
    buildProjectStylePayload,
    project,
    projectId,
    settings
  ]);

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
    setExportError(null);
    setExportHeading("Exporting video");
    setExportProgressPct(0);
    setExportProgressMessage("");
    setExportChecklist([]);
    setIsExporting(false);
    setExportOutputPath(null);
    setCanUndoEdit(false);
    editHistoryRef.current = [];
    editHistoryIndexRef.current = 0;
    lastHistoryCommitAtRef.current = 0;
    shouldResumePlaybackRef.current = false;
    setCreateSubtitlesJobStream((prev) => {
      prev?.close();
      return null;
    });
    setExportJobStream((prev) => {
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
      setCanUndoEdit(false);
      editHistoryRef.current = [];
      editHistoryIndexRef.current = 0;
      lastHistoryCommitAtRef.current = 0;
      shouldResumePlaybackRef.current = false;
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
    return () => {
      exportJobStream?.close();
    };
  }, [exportJobStream]);

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
      subtitle_mode: appearance.subtitle_mode,
      highlight_color: appearance.highlight_color
    };
  }, [appearance.highlight_color, appearance.subtitle_mode]);

  const resolveOutputDir = React.useCallback(
    async (
      videoInputPath: string,
      reportError?: (message: string) => void
    ): Promise<string | null> => {
      if (!settings) {
        return null;
      }
      const setErrorMessage = reportError ?? (() => {});
      if (settings.save_policy === "same_folder") {
        return getDirName(videoInputPath);
      }
      if (settings.save_policy === "fixed_folder") {
        if (settings.save_folder) {
          return settings.save_folder;
        }
        setErrorMessage("Choose a folder in Settings to save your subtitles.");
        return null;
      }
      if (!isTauriEnv) {
        setErrorMessage("Choose a folder in Settings to save your subtitles.");
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

  const updateExportChecklist = React.useCallback(
    (stepId: string, stateValue: string, reason?: string) => {
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
      setExportChecklist((prev) =>
        prev.map((item) =>
          item.id === stepId ? { ...item, state: mappedState, detail: reason ?? item.detail } : item
        )
      );
    },
    []
  );

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
    if (!projectId || !project?.video?.path || isCreatingSubtitles || isExporting) {
      return;
    }
    if (!settings) {
      setCreateSubtitlesError("Settings are still loading. Please try again.");
      return;
    }

    const resolvedOutputDir = await resolveOutputDir(project.video.path, setCreateSubtitlesError);
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
    isExporting,
    project,
    projectId,
    resolveOutputDir,
    settings
  ]);

  const cancelCreateSubtitles = React.useCallback(async () => {
    await createSubtitlesJobStream?.cancel();
  }, [createSubtitlesJobStream]);

  const handleExportEvent = React.useCallback(
    (event: JobEvent) => {
      if (event.type === "started") {
        setExportHeading(event.heading ?? "Exporting video");
        return;
      }
      if (event.type === "checklist") {
        updateExportChecklist(event.step_id, event.state, resolveChecklistReason(event));
        return;
      }
      if (event.type === "progress") {
        if (typeof event.pct === "number") {
          setExportProgressPct(event.pct);
        }
        if (event.message) {
          setExportProgressMessage(event.message);
        }
        return;
      }
      if (event.type === "result") {
        const payload = event.payload ?? {};
        if (typeof payload.output_path === "string") {
          setExportOutputPath(payload.output_path);
        }
        return;
      }
      if (event.type === "completed") {
        setExportProgressPct(100);
        setIsExporting(false);
        setExportJobStream((prev) => {
          prev?.close();
          return null;
        });
        setProjectReloadTick((prev) => prev + 1);
        return;
      }
      if (event.type === "cancelled") {
        setExportProgressPct(0);
        setExportProgressMessage("");
        setIsExporting(false);
        if (event.message) {
          setExportError(event.message);
        }
        setExportJobStream((prev) => {
          prev?.close();
          return null;
        });
        return;
      }
      if (event.type === "error") {
        setExportProgressPct(0);
        setExportProgressMessage("");
        setIsExporting(false);
        setExportError(event.message ?? "Video export failed.");
        setExportJobStream((prev) => {
          prev?.close();
          return null;
        });
      }
    },
    [resolveChecklistReason, updateExportChecklist]
  );

  const startExport = React.useCallback(async () => {
    if (!projectId || !project?.video?.path || isExporting || isCreatingSubtitles) {
      return;
    }
    if (!settings) {
      setExportError("Settings are still loading. Please try again.");
      return;
    }
    if (
      appearance.subtitle_mode === "word_highlight" &&
      (project.status === "needs_subtitles" || project.status === "missing_file")
    ) {
      setExportError(
        "Word highlight export needs synced timings. Run Create subtitles again before exporting."
      );
      return;
    }
    const resolvedOutputDir = await resolveOutputDir(project.video.path, setExportError);
    if (!resolvedOutputDir) {
      return;
    }

    try {
      await updateProject(projectId, {
        style: buildProjectStylePayload(appearance, preset, highlightOpacity)
      });
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Failed to save style before export.");
      return;
    }
    setExportError(null);
    setExportHeading("Exporting video");
    setExportProgressPct(0);
    setExportProgressMessage("Starting...");
    setExportChecklist(defaultChecklist(buildExportChecklist()));
    setIsExporting(true);
    try {
      const job = await createVideoWithSubtitlesJob(
        {
          projectId,
          outputDir: resolvedOutputDir,
          options: buildJobOptions(settings)
        },
        {
          onEvent: handleExportEvent,
          onError: () => {
            setIsExporting(false);
            setExportError("Connection lost while streaming job updates.");
            setExportJobStream((prev) => {
              prev?.close();
              return null;
            });
          }
        }
      );
      setExportJobStream(job);
    } catch (err) {
      setIsExporting(false);
      setExportError(err instanceof Error ? err.message : "Failed to start video export.");
    }
  }, [
    appearance.subtitle_mode,
    buildProjectStylePayload,
    buildJobOptions,
    handleExportEvent,
    isCreatingSubtitles,
    isExporting,
    preset,
    project,
    projectId,
    resolveOutputDir,
    settings,
    appearance,
    highlightOpacity
  ]);

  const cancelExport = React.useCallback(async () => {
    await exportJobStream?.cancel();
  }, [exportJobStream]);

  React.useEffect(() => {
    if (!pendingAutoStartSubtitles) {
      return;
    }
    if (isLoading || !project || !settings || isCreatingSubtitles || isExporting) {
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
    isExporting,
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
  const latestOutputPath = exportOutputPath ?? project?.latest_export?.output_video_path ?? null;
  const canExport =
    hasSubtitles &&
    !isCreatingSubtitles &&
    !isExporting &&
    (project?.status === "ready" || project?.status === "done");
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
  const hasStyledSubtitleBackground =
    appearance.background_mode === "line" || appearance.background_mode === "word";

  const openLatestOutputVideo = React.useCallback(async () => {
    if (latestOutputPath) {
      await openPath(latestOutputPath);
    }
  }, [latestOutputPath]);

  const openLatestOutputFolder = React.useCallback(async () => {
    if (!latestOutputPath) {
      return;
    }
    await openPath(getDirName(latestOutputPath));
  }, [latestOutputPath]);

  const subtitleVerticalClass =
    appearance.vertical_anchor === "top"
      ? "items-start"
      : appearance.vertical_anchor === "middle"
        ? "items-center"
        : "items-end";

  const subtitleOverlayPositionStyle = React.useMemo<React.CSSProperties>(() => {
    const offsetPx = `${Math.max(0, appearance.vertical_offset)}px`;
    let style: React.CSSProperties;
    if (appearance.vertical_anchor === "top") {
      style = { paddingTop: offsetPx };
    } else if (appearance.vertical_anchor === "middle") {
      style = { transform: `translateY(${Math.round(appearance.vertical_offset)}px)` };
    } else {
      style = { paddingBottom: offsetPx };
    }
    return style;
  }, [appearance.vertical_anchor, appearance.vertical_offset]);

  const subtitlePreviewTextStyle = React.useMemo<React.CSSProperties>(() => {
    const style: React.CSSProperties = {
      fontFamily: appearance.font_family || DEFAULT_APPEARANCE.font_family,
      fontSize: `${Math.max(10, appearance.font_size)}px`,
      fontWeight: appearance.font_style === "bold" ? 700 : 400,
      fontStyle: appearance.font_style === "italic" ? "italic" : "normal",
      letterSpacing: `${appearance.letter_spacing}px`,
      color: colorWithOpacity(appearance.text_color, appearance.text_opacity)
    };

    const shadows: string[] = [];
    if (appearance.outline_enabled && appearance.outline_width > 0) {
      shadows.push(...buildOutlineShadows(appearance.outline_color, appearance.outline_width));
    }
    if (appearance.shadow_enabled && appearance.shadow_strength > 0) {
      const blurRadius = Math.max(0, Math.round(appearance.shadow_strength * 1.5));
      shadows.push(
        `${appearance.shadow_offset_x}px ${appearance.shadow_offset_y}px ${blurRadius}px ${colorWithOpacity(
          appearance.shadow_color,
          appearance.shadow_opacity
        )}`
      );
    }
    if (shadows.length > 0) {
      style.textShadow = shadows.join(", ");
    }

    const useLineBackground = appearance.background_mode === "line";
    if (useLineBackground) {
      const backgroundColor = colorWithOpacity(appearance.line_bg_color, appearance.line_bg_opacity);
      const padding = appearance.line_bg_padding;
      const radius = appearance.line_bg_radius;
      style.backgroundColor = backgroundColor;
      style.padding = `${Math.max(0, padding)}px`;
      style.borderRadius = `${Math.max(0, radius)}px`;
    }

    return style;
  }, [appearance]);

  React.useEffect(() => {
    if (!isEditingActiveCue) {
      return;
    }
    const textarea = activeSubtitleRef.current;
    if (!textarea) {
      return;
    }
    if (document.activeElement !== textarea) {
      textarea.focus();
    }
  }, [activeCue, isEditingActiveCue]);

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
      if (!projectId) {
        return;
      }
      try {
        await updateProject(
          projectId,
          {
            style: buildProjectStylePayload(
              nextAppearance,
              nextPreset,
              nextHighlightOpacity
            )
          }
        );
        setStyleError(null);
      } catch (err) {
        setStyleError(err instanceof Error ? err.message : "Failed to save style settings.");
      }
    },
    [buildProjectStylePayload, projectId]
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
    if (isExporting) {
      return;
    }
    setAppearance((prev) => {
      const next = { ...prev, ...changes };
      customAppearanceRef.current = next;
      const nextPreset = preset === "Custom" ? preset : "Custom";
      debouncedPersistStyle(next, nextPreset, highlightOpacity);
      return next;
    });
    if (preset !== "Custom") {
      setPreset("Custom");
    }
  };

  const handlePresetChange = (nextPreset: string) => {
    if (isExporting) {
      return;
    }
    if (preset === "Custom") {
      customAppearanceRef.current = appearance;
    }
    const nextAppearance =
      nextPreset === "Custom"
        ? { ...customAppearanceRef.current }
        : applyPresetAppearance(appearance, nextPreset);
    setPreset(nextPreset);
    setAppearance(nextAppearance);
    debouncedPersistStyle(nextAppearance, nextPreset, highlightOpacity);
  };

  const handleHighlightOpacityChange = (nextHighlightOpacity: number) => {
    if (isExporting) {
      return;
    }
    setHighlightOpacity(nextHighlightOpacity);
    debouncedPersistStyle(appearance, preset, nextHighlightOpacity);
  };

  const handleResetPreset = () => {
    if (isExporting) {
      return;
    }
    const targetPreset = preset === "Custom" ? "Default" : preset;
    const nextAppearance = applyPresetAppearance(appearance, targetPreset);
    setPreset(targetPreset);
    setAppearance(nextAppearance);
    customAppearanceRef.current = nextAppearance;
    void persistStyleSettings(nextAppearance, targetPreset, highlightOpacity);
  };

  const initializeEditHistory = React.useCallback((initialText: string) => {
    editHistoryRef.current = [initialText];
    editHistoryIndexRef.current = 0;
    lastHistoryCommitAtRef.current = Date.now();
    setCanUndoEdit(false);
  }, []);

  const updateEditHistory = React.useCallback((nextText: string) => {
    const now = Date.now();
    const history = editHistoryRef.current;
    const index = editHistoryIndexRef.current;
    const truncatedHistory = history.slice(0, index + 1);
    const previousText = truncatedHistory[truncatedHistory.length - 1] ?? "";
    if (previousText === nextText) {
      editHistoryRef.current = truncatedHistory;
      editHistoryIndexRef.current = truncatedHistory.length - 1;
      setCanUndoEdit(editHistoryIndexRef.current > 0);
      return;
    }
    const lengthDelta = Math.abs(nextText.length - previousText.length);
    const canCoalesceTypingBurst =
      truncatedHistory.length > 1 &&
      index === truncatedHistory.length - 1 &&
      now - lastHistoryCommitAtRef.current < EDIT_UNDO_COALESCE_MS &&
      lengthDelta <= 2;
    if (canCoalesceTypingBurst) {
      truncatedHistory[truncatedHistory.length - 1] = nextText;
    } else {
      truncatedHistory.push(nextText);
    }
    editHistoryRef.current = truncatedHistory;
    editHistoryIndexRef.current = truncatedHistory.length - 1;
    lastHistoryCommitAtRef.current = now;
    setCanUndoEdit(editHistoryIndexRef.current > 0);
  }, []);

  const resetEditSessionState = React.useCallback(() => {
    setCanUndoEdit(false);
    editHistoryRef.current = [];
    editHistoryIndexRef.current = 0;
    lastHistoryCommitAtRef.current = 0;
  }, []);

  const resumePlaybackIfNeeded = React.useCallback(() => {
    if (!shouldResumePlaybackRef.current) {
      return;
    }
    shouldResumePlaybackRef.current = false;
    const videoElement = videoRef.current;
    if (!videoElement) {
      return;
    }
    const playPromise = videoElement.play();
    if (playPromise && typeof playPromise.catch === "function") {
      playPromise.catch(() => {});
    }
  }, []);

  const beginEditingCue = React.useCallback(
    (cue: SrtCue, resumePlaybackOnExit: boolean) => {
      shouldResumePlaybackRef.current = resumePlaybackOnExit;
      setSelectedCueId(cue.id);
      setEditingCueId(cue.id);
      setEditingText(cue.text);
      setEditError(null);
      initializeEditHistory(cue.text);
    },
    [initializeEditHistory]
  );

  const handleEditTextChange = React.useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const nextText = event.target.value;
      setEditingText(nextText);
      updateEditHistory(nextText);
    },
    [updateEditHistory]
  );

  const handleUndoEdit = React.useCallback(() => {
    if (isSavingCue || isExporting) {
      return;
    }
    const index = editHistoryIndexRef.current;
    if (index <= 0) {
      return;
    }
    const nextIndex = index - 1;
    editHistoryIndexRef.current = nextIndex;
    setEditingText(editHistoryRef.current[nextIndex] ?? "");
    lastHistoryCommitAtRef.current = Date.now();
    setCanUndoEdit(nextIndex > 0);
  }, [isExporting, isSavingCue]);

  const handleCancelEdit = React.useCallback(() => {
    setSelectedCueId(null);
    setEditingCueId(null);
    setEditingText("");
    setEditError(null);
    resetEditSessionState();
    resumePlaybackIfNeeded();
  }, [resetEditSessionState, resumePlaybackIfNeeded]);

  const handleSaveEdit = React.useCallback(async () => {
    if (!projectId || !editingCueId || isExporting) {
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
      setSelectedCueId(null);
      setEditingCueId(null);
      setEditingText("");
      setEditError(null);
      resetEditSessionState();
      resumePlaybackIfNeeded();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to save subtitle changes.");
    } finally {
      setIsSavingCue(false);
    }
  }, [
    cues,
    editingCueId,
    editingText,
    isExporting,
    projectId,
    resetEditSessionState,
    resumePlaybackIfNeeded
  ]);

  const handleCueClick = React.useCallback(
    (cue: SrtCue) => {
      if (isSavingCue || isExporting) {
        return;
      }
      const videoElement = videoRef.current;
      const isPlaying = Boolean(videoElement && !videoElement.paused && !videoElement.ended);
      if (isPlaying) {
        videoElement?.pause();
      }
      beginEditingCue(cue, isPlaying);
    },
    [beginEditingCue, isExporting, isSavingCue]
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
    if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "z") {
      event.preventDefault();
      handleUndoEdit();
      return;
    }
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
    <div
      className={cn(
        "px-4 pb-2 pl-5 pr-5",
        isExporting ? "pointer-events-none opacity-60" : ""
      )}
    >
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
    </div>
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
                  disabled={isExporting}
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
                  disabled={isExporting}
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
                <div className="relative h-full w-full overflow-hidden rounded-md">
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
                  {activeCue && (() => {
                    const lineCount = (activeCue.text.match(/\n/g) ?? []).length + 1;
                    const cueSegments = activeCue.text.split(/(\s+)/);
                    const cueWordCount = cueSegments.reduce(
                      (count, segment) => count + (/\S/.test(segment) ? 1 : 0),
                      0
                    );
                    const cueDuration = Math.max(0.001, activeCue.endSeconds - activeCue.startSeconds);
                    const cueProgress = Math.max(
                      0,
                      Math.min(1, (currentTimeSeconds - activeCue.startSeconds) / cueDuration)
                    );
                    const highlightedWordIndex =
                      appearance.subtitle_mode === "word_highlight" && cueWordCount > 0
                        ? Math.min(cueWordCount - 1, Math.floor(cueProgress * cueWordCount))
                        : -1;
                    const highlightWordColor = colorWithOpacity(
                      appearance.highlight_color,
                      highlightOpacity
                    );
                    const wordPaddingX = Math.max(0, appearance.word_bg_padding / 2);
                    const hasWordBackground = appearance.background_mode === "word";
                    const hasRtlChars = RTL_CHAR_PATTERN.test(activeCue.text);
                    const activeWordStyle: React.CSSProperties = hasWordBackground
                      ? {
                          backgroundColor: colorWithOpacity(
                            appearance.word_bg_color,
                            appearance.word_bg_opacity
                          ),
                          borderRadius: `${Math.max(0, appearance.word_bg_radius)}px`,
                          boxShadow: `0 0 0 ${wordPaddingX}px ${colorWithOpacity(
                            appearance.word_bg_color,
                            appearance.word_bg_opacity
                          )}`
                        }
                      : {};
                    const subtitleDirection: "rtl" | "auto" = hasRtlChars ? "rtl" : "auto";
                    return (
                    <div
                      className={cn(
                        "pointer-events-none absolute inset-0 flex justify-center px-4",
                        subtitleVerticalClass
                      )}
                      style={subtitleOverlayPositionStyle}
                    >
                      <div className="pointer-events-auto w-full max-w-[720px]">
                        {isEditingActiveCue ? (
                          <textarea
                            ref={activeSubtitleRef}
                            data-testid="workbench-subtitle-editor"
                            className="w-full resize-none overflow-hidden rounded-md border border-primary/70 bg-background/25 px-3 py-2 text-center shadow-lg ring-1 ring-primary/45 transition focus-visible:outline-none"
                            style={subtitlePreviewTextStyle}
                            value={editingText}
                            onChange={handleEditTextChange}
                            onKeyDown={handleEditorKeyDown}
                            rows={Math.max(2, Math.min(4, lineCount))}
                            readOnly={isSavingCue || isExporting}
                            aria-label="Active subtitle editor"
                          />
                        ) : (
                          <div
                            role="button"
                            tabIndex={0}
                            data-testid="workbench-active-subtitle"
                            className={cn(
                              "w-full cursor-text rounded-md border border-transparent bg-transparent px-3 py-2 text-center text-base font-medium leading-snug text-white shadow-lg transition focus-visible:outline-none hover:border-primary/55 hover:ring-1 hover:ring-primary/40",
                              isActiveCueSelected
                                ? "outline-2 outline-offset-2 outline-primary border-primary/65 ring-1 ring-primary/50"
                                : "outline-none"
                            )}
                            style={subtitlePreviewTextStyle}
                            onClick={() => handleCueClick(activeCue)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                handleCueClick(activeCue);
                              }
                            }}
                            aria-label="Active subtitle editor"
                          >
                            <span
                              className="whitespace-pre-wrap"
                              dir={subtitleDirection}
                              style={{ unicodeBidi: "plaintext" }}
                            >
                              {appearance.subtitle_mode === "word_highlight" && cueWordCount > 0
                                ? (() => {
                                    let seenWordIndex = -1;
                                    return cueSegments.map((segment, idx) => {
                                      const isWord = /\S/.test(segment);
                                      if (isWord) {
                                        seenWordIndex += 1;
                                      }
                                      const isActiveWord =
                                        isWord && seenWordIndex === highlightedWordIndex;
                                      return (
                                        <span
                                          key={`${idx}-${segment}`}
                                          style={
                                            isActiveWord
                                              ? { ...activeWordStyle, color: highlightWordColor }
                                              : undefined
                                          }
                                        >
                                          {segment}
                                        </span>
                                      );
                                    });
                                  })()
                                : activeCue.text}
                            </span>
                          </div>
                        )}
                        {isEditingActiveCue && (
                          <div className="mt-2 flex items-center justify-end gap-2">
                            <Button
                              type="button"
                              variant="secondary"
                              size="icon"
                              className="h-8 w-8 border border-border/70 bg-background/90"
                              aria-label="Undo subtitle edit"
                              title="Undo"
                              data-testid="workbench-subtitle-undo"
                              onClick={handleUndoEdit}
                              disabled={isSavingCue || isExporting || !canUndoEdit}
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                            <Button
                              type="button"
                              variant="secondary"
                              size="icon"
                              className="h-8 w-8 border border-border/70 bg-background/90"
                              aria-label="Cancel subtitle edit"
                              title="Cancel"
                              data-testid="workbench-subtitle-cancel"
                              onClick={handleCancelEdit}
                              disabled={isSavingCue || isExporting}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                            <Button
                              type="button"
                              variant="default"
                              size="icon"
                              className="h-8 w-8"
                              aria-label="Save subtitle edit"
                              title="Save"
                              data-testid="workbench-subtitle-save"
                              onClick={() => void handleSaveEdit()}
                              disabled={isSavingCue || isExporting}
                            >
                              <Check className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                    );
                  })()}
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
                className="flex min-h-0 w-88 shrink-0 flex-col rounded-lg border border-border bg-card xl:w-96"
                data-testid="workbench-right-panel"
              >
                <div className="border-b border-border px-4 py-2">
                  <h2 className="text-sm font-semibold">Style</h2>
                </div>
                <div
                  data-testid="workbench-style-scroll-panel"
                  className="min-h-0 flex-1 overflow-x-visible overflow-y-auto py-3"
                  style={{ scrollbarGutter: "stable" }}
                >
                  {stylePanelContent}
                </div>
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
              className="fixed inset-y-0 right-0 z-50 flex w-[min(92vw,360px)] flex-col border-l border-border bg-card shadow-lg"
              data-testid="workbench-right-drawer"
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-2">
                <h2 className="text-sm font-semibold">Style</h2>
                <Button variant="ghost" size="sm" onClick={() => setRightOverlayOpen(false)}>
                  Close
                </Button>
              </div>
              <div
                data-testid="workbench-style-scroll-drawer"
                className="min-h-0 flex-1 overflow-x-visible overflow-y-auto py-3"
                style={{ scrollbarGutter: "stable" }}
              >
                {stylePanelContent}
              </div>
            </aside>
          )}

          {hasSubtitles && (
            <section
              className="rounded-lg border border-border bg-card p-4"
              data-testid="workbench-export-panel"
            >
              {exportError && (
                <div className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                  {exportError}
                </div>
              )}
              {isExporting ? (
                <div className="space-y-3">
                  <p className="text-sm font-semibold text-foreground">{exportHeading}</p>
                  {exportChecklist.length > 0 && (
                    <Checklist items={exportChecklist} className="text-left" />
                  )}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{Math.round(exportProgressPct)}%</span>
                      <span className="truncate">{exportProgressMessage}</span>
                    </div>
                    <Progress value={exportProgressPct} />
                  </div>
                  <div className="flex justify-center">
                    <Button
                      variant="secondary"
                      data-testid="workbench-cancel-export"
                      onClick={() => void cancelExport()}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground">
                      Create video with subtitles
                    </p>
                    {latestOutputPath ? (
                      <p className="truncate text-xs text-muted-foreground">
                        Latest export: {latestOutputPath}
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Export a final video with your current subtitles and style.
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {latestOutputPath && (
                      <Button
                        variant="secondary"
                        size="sm"
                        data-testid="workbench-play-export-video"
                        onClick={() => void openLatestOutputVideo()}
                      >
                        Play video
                      </Button>
                    )}
                    {latestOutputPath && (
                      <Button
                        variant="secondary"
                        size="sm"
                        data-testid="workbench-open-export-folder"
                        onClick={() => void openLatestOutputFolder()}
                      >
                        Open folder
                      </Button>
                    )}
                    <Button
                      size="sm"
                      data-testid="workbench-export-cta"
                      onClick={() => void startExport()}
                      disabled={!canExport}
                    >
                      Create video with subtitles
                    </Button>
                  </div>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
};

export default Workbench;
