import * as React from "react";
import {
  Check,
  Minus,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Volume2,
  VolumeX,
  X
} from "lucide-react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import Checklist, { ChecklistItem } from "@/components/Checklist";
import { useToast } from "@/contexts/ToastContext";
import StyleControls from "@/components/SubtitleStyle/StyleControls";
import { WorkbenchSkeleton } from "@/components/WorkbenchSkeleton";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Slider } from "@/components/ui/slider";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
  buildExportChecklist,
  buildGenerateChecklist,
  checklistStepIds
} from "@/legacyCopy";
import {
  attachToJobEvents,
  cancelJob,
  createSubtitlesJob,
  createVideoWithSubtitlesJob,
  JobConflictError,
  JobEvent,
  JobEventStream
} from "@/jobsClient";
import {
  fetchProject,
  fetchProjectWordTimings,
  fetchProjectSubtitles,
  ProjectManifest,
  ProjectWordTimingsDocument,
  updateProject
} from "@/projectsClient";
import { useRunningJobs } from "@/contexts/RunningJobsContext";
import { useWindowHeight } from "@/hooks/useWindowHeight";
import { useWindowWidth } from "@/hooks/useWindowWidth";
import {
  clearPersistedRunningJob,
  getPersistedRunningJob,
  setPersistedRunningJob
} from "@/lib/runningJobPersistence";
import { useWorkbenchTabs } from "@/workbenchTabs";
import { parseSrt, serializeSrt, SrtCue } from "@/lib/srt";
import { messageForBackendError } from "@/backendHealth";
import {
  fetchSettings,
  previewOverlay,
  SettingsConfig,
  SubtitleStyleAppearance
} from "@/settingsClient";

type WorkbenchLocationState = {
  autoStartSubtitles?: boolean;
  cancelledCreateProjectId?: string;
  cancelledCreateProjectTitle?: string;
} | null;

type WorkbenchProps = {
  /** When provided (e.g. from TabHost), used instead of route params so the same instance can stay mounted. */
  projectId?: string;
};

const STATUS_LABELS: Record<string, string> = {
  needs_video: "Needs video",
  needs_subtitles: "Not started",
  ready: "Ready to review",
  exporting: "Exporting",
  done: "Exported",
  missing_file: "Missing file"
};

const CREATE_SUBTITLES_FILE_NOT_FOUND_MESSAGE =
  "The video file wasn't found. If you renamed or moved it, relink the video from the project hub and try again.";

function normalizeCreateSubtitlesErrorMessage(raw: string | null | undefined): string {
  if (raw == null || typeof raw !== "string") return raw ?? "Subtitle generation failed.";
  const isFileNotFound =
    raw.includes("No such file or directory") || raw.includes("Error opening input");
  return isFileNotFound ? CREATE_SUBTITLES_FILE_NOT_FOUND_MESSAGE : raw;
}

const ELEVATOR_MUSIC_TRACK_NAMES = [
  "fogged-glass-reverie.mp3",
  "breezy-afternoon.mp3",
  "lantern-light-bistro.mp3"
];

const getElevatorMusicTrackUrl = (name: string) => {
  const base = typeof import.meta.env.BASE_URL === "string" ? import.meta.env.BASE_URL : "/";
  const path = base.endsWith("/") ? `${base}elevator-music/${name}` : `${base}/elevator-music/${name}`;
  return path.startsWith("/") ? path : `/${path}`;
};

const getFileName = (value?: string | null) => {
  if (!value) {
    return "Untitled video";
  }
  const parts = value.split(/[/\\]/);
  return parts[parts.length - 1] ?? value;
};

const resolveTitle = (project: ProjectManifest | null) => {
  const filename = project?.video?.filename ?? project?.video?.path ?? "";
  return filename ? getFileName(filename) : "Untitled video";
};

const resolveStatusLabel = (status?: string | null) => {
  if (!status) {
    return "Loading";
  }
  return STATUS_LABELS[status] ?? "Not started";
};

const formatTime = (seconds: number): string => {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
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
  font_family: "Heebo",
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
  shadow_blur: 6,
  background_mode: "none",
  line_bg_color: "#000000",
  line_bg_opacity: 0.7,
  line_bg_padding: 8,
  line_bg_padding_top: 8,
  line_bg_padding_right: 8,
  line_bg_padding_bottom: 8,
  line_bg_padding_left: 8,
  line_bg_padding_linked: true,
  line_bg_radius: 0,
  word_bg_color: "#000000",
  word_bg_opacity: 0.4,
  word_bg_padding: 8,
  word_bg_padding_top: 8,
  word_bg_padding_right: 8,
  word_bg_padding_bottom: 8,
  word_bg_padding_left: 8,
  word_bg_padding_linked: true,
  word_bg_radius: 0,
  vertical_anchor: "bottom",
  vertical_offset: 28,
  subtitle_mode: "word_highlight",
  highlight_color: "#FFD400"
};

export const NAMED_PRESET_IDS = [
  "classic_static",
  "bold_outline_static",
  "boxed_static",
  "lift_static",
  "neon_karaoke",
  "boxed_karaoke"
] as const;

export type NamedPresetId = (typeof NAMED_PRESET_IDS)[number];

const PRESET_DEFINITIONS: Record<NamedPresetId, SubtitleStyleAppearance> = {
  classic_static: {
    ...DEFAULT_APPEARANCE,
    subtitle_mode: "static",
    font_family: "Heebo",
    font_size: 45,
    font_style: "regular",
    text_color: "#FFFFFF",
    text_opacity: 1,
    letter_spacing: 0,
    outline_enabled: true,
    outline_width: 2.5,
    outline_color: "#000000",
    shadow_enabled: true,
    shadow_strength: 2,
    shadow_offset_x: 0,
    shadow_offset_y: 2,
    shadow_color: "#000000",
    shadow_opacity: 0.3,
    shadow_blur: 6,
    background_mode: "none",
    vertical_anchor: "bottom",
    vertical_offset: 40
  },
  bold_outline_static: {
    ...DEFAULT_APPEARANCE,
    subtitle_mode: "static",
    font_family: "Heebo",
    font_size: 51,
    font_style: "regular",
    text_color: "#FFFFFF",
    text_opacity: 1,
    letter_spacing: 0,
    outline_enabled: true,
    outline_width: 5.5,
    outline_color: "#000000",
    shadow_enabled: false,
    shadow_strength: 0,
    shadow_offset_x: 0,
    shadow_offset_y: 0,
    shadow_color: "#000000",
    shadow_opacity: 0,
    shadow_blur: 0,
    background_mode: "none",
    vertical_anchor: "bottom",
    vertical_offset: 40
  },
  boxed_static: {
    ...DEFAULT_APPEARANCE,
    subtitle_mode: "static",
    font_family: "Heebo",
    font_size: 45,
    font_style: "regular",
    text_color: "#FFFFFF",
    text_opacity: 1,
    letter_spacing: 0,
    outline_enabled: true,
    outline_width: 1.5,
    outline_color: "#000000",
    shadow_enabled: false,
    shadow_strength: 0,
    shadow_offset_x: 0,
    shadow_offset_y: 0,
    shadow_color: "#000000",
    shadow_opacity: 0,
    shadow_blur: 0,
    background_mode: "line",
    line_bg_color: "#000000",
    line_bg_opacity: 0.5,
    line_bg_padding: 10,
    line_bg_padding_top: 10,
    line_bg_padding_right: 10,
    line_bg_padding_bottom: 10,
    line_bg_padding_left: 10,
    line_bg_radius: 10,
    vertical_anchor: "bottom",
    vertical_offset: 40
  },
  lift_static: {
    ...DEFAULT_APPEARANCE,
    subtitle_mode: "static",
    font_family: "Heebo",
    font_size: 45,
    font_style: "regular",
    text_color: "#FFFFFF",
    text_opacity: 1,
    letter_spacing: 0,
    outline_enabled: true,
    outline_width: 2.5,
    outline_color: "#000000",
    shadow_enabled: true,
    shadow_strength: 2.5,
    shadow_offset_x: 2,
    shadow_offset_y: 2,
    shadow_color: "#000000",
    shadow_opacity: 0.85,
    shadow_blur: 8,
    background_mode: "none",
    vertical_anchor: "bottom",
    vertical_offset: 40
  },
  neon_karaoke: {
    ...DEFAULT_APPEARANCE,
    subtitle_mode: "word_highlight",
    font_family: "Heebo",
    font_size: 45,
    font_style: "regular",
    text_color: "#FFFFFF",
    text_opacity: 1,
    letter_spacing: 0,
    outline_enabled: true,
    outline_width: 3.5,
    outline_color: "#000000",
    shadow_enabled: true,
    shadow_strength: 2.5,
    shadow_offset_x: 0,
    shadow_offset_y: 2,
    shadow_color: "#000000",
    shadow_opacity: 0.3,
    shadow_blur: 8,
    background_mode: "none",
    highlight_color: "#00E5FF",
    vertical_anchor: "bottom",
    vertical_offset: 40
  },
  boxed_karaoke: {
    ...DEFAULT_APPEARANCE,
    subtitle_mode: "word_highlight",
    font_family: "Heebo",
    font_size: 45,
    font_style: "regular",
    text_color: "#FFFFFF",
    text_opacity: 1,
    letter_spacing: 0,
    outline_enabled: true,
    outline_width: 1.5,
    outline_color: "#000000",
    shadow_enabled: true,
    shadow_strength: 1,
    shadow_offset_x: 0,
    shadow_offset_y: 0,
    shadow_color: "#000000",
    shadow_opacity: 0.2,
    shadow_blur: 6,
    background_mode: "word",
    word_bg_color: "#000000",
    word_bg_opacity: 0.48,
    word_bg_padding: 10,
    word_bg_padding_top: 10,
    word_bg_padding_right: 10,
    word_bg_padding_bottom: 10,
    word_bg_padding_left: 10,
    word_bg_radius: 10,
    highlight_color: "#FFD400",
    vertical_anchor: "bottom",
    vertical_offset: 40
  }
};

const isNamedPresetId = (value: string): value is NamedPresetId =>
  NAMED_PRESET_IDS.includes(value as NamedPresetId);

function migrateAppearancePadding(
  a: SubtitleStyleAppearance
): SubtitleStyleAppearance {
  const top = a.line_bg_padding_top ?? a.line_bg_padding ?? 8;
  const right = a.line_bg_padding_right ?? a.line_bg_padding ?? 8;
  const bottom = a.line_bg_padding_bottom ?? a.line_bg_padding ?? 8;
  const left = a.line_bg_padding_left ?? a.line_bg_padding ?? 8;
  const wTop = a.word_bg_padding_top ?? a.word_bg_padding ?? 8;
  const wRight = a.word_bg_padding_right ?? a.word_bg_padding ?? 8;
  const wBottom = a.word_bg_padding_bottom ?? a.word_bg_padding ?? 8;
  const wLeft = a.word_bg_padding_left ?? a.word_bg_padding ?? 8;
  return {
    ...a,
    line_bg_padding_top: top,
    line_bg_padding_right: right,
    line_bg_padding_bottom: bottom,
    line_bg_padding_left: left,
    word_bg_padding_top: wTop,
    word_bg_padding_right: wRight,
    word_bg_padding_bottom: wBottom,
    word_bg_padding_left: wLeft,
    line_bg_padding_linked: a.line_bg_padding_linked ?? true,
    word_bg_padding_linked: a.word_bg_padding_linked ?? true
  };
}

const applyPresetAppearance = (
  presetId: string
): SubtitleStyleAppearance | null => {
  if (presetId === "Custom" || !isNamedPresetId(presetId)) {
    return null;
  }
  return { ...PRESET_DEFINITIONS[presetId] };
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
const MAX_OUTLINE_SHADOW_RADIUS = 10;
const SUBTITLE_EDITOR_CONTROLS_GAP_PX = 8;
const SUBTITLE_CONTROLS_COLLISION_GAP_PX = 8;
const SUBTITLE_CONTROLS_PUSH_TOLERANCE_PX = 0.5;
const QT_POINT_TO_CSS_PX = 96 / 72;
const WEB_SUBTITLE_LINE_HEIGHT_RATIO = 1.375;
const QT_SUBTITLE_LINE_HEIGHT_RATIO = 1.125;
const ACTIVE_TASK_SYNC_POLL_MS = 2500;
const PREPARING_PREVIEW_MIN_ACTIVE_MS = 5000;
const PREPARING_PREVIEW_DONE_VISIBLE_MS = 150;
const STREAM_ATTACH_COOLDOWN_MS = 10_000;
const ALIGNMENT_PROGRESS_STEP_IDS = new Set(["ALIGN_WORDS", checklistStepIds.timingWordHighlights]);
const ALIGNMENT_WORD_DETAIL_PATTERN = /^(\d{1,3}(?:,\d{3})*|\d+)\s*\/\s*(\d{1,3}(?:,\d{3})*|\d+)\s+words$/i;

type StreamHealth = "idle" | "connecting" | "open" | "cooldown";

type TimingFallbackProgress = {
  current: number;
  total: number;
  updatedAtMs: number;
};

type ParsedAlignmentWordDetail = {
  current: number;
  total: number;
};

const defaultChecklist = (items: { id: string; label: string }[]): ChecklistItem[] =>
  items.map((item) => ({ ...item, state: "pending" }));

const isChecklistState = (value: unknown): value is NonNullable<ChecklistItem["state"]> =>
  value === "pending" ||
  value === "active" ||
  value === "done" ||
  value === "skipped" ||
  value === "failed";

const normalizeChecklistState = (value: unknown): NonNullable<ChecklistItem["state"]> => {
  if (value === "start") {
    return "active";
  }
  if (isChecklistState(value)) {
    return value;
  }
  return "pending";
};

const asString = (value: unknown): string | null => (typeof value === "string" ? value : null);

const asNonEmptyString = (value: unknown): string | null => {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const parseIsoTimestampMs = (value: unknown): number => {
  if (typeof value !== "string" || !value.trim()) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const parseAlignmentWordDetail = (value: unknown): ParsedAlignmentWordDetail | null => {
  if (typeof value !== "string") {
    return null;
  }
  const match = value.trim().match(ALIGNMENT_WORD_DETAIL_PATTERN);
  if (!match) {
    return null;
  }
  const current = Number.parseInt(match[1].replace(/,/g, ""), 10);
  const total = Number.parseInt(match[2].replace(/,/g, ""), 10);
  if (!Number.isFinite(current) || !Number.isFinite(total) || total <= 0) {
    return null;
  }
  return {
    current: Math.max(0, current),
    total
  };
};

const formatAlignmentWordDetail = (current: number, total: number): string => {
  const safeTotal = Math.max(1, Math.floor(total));
  const safeCurrent = Math.max(0, Math.min(Math.floor(current), safeTotal));
  return `${safeCurrent.toLocaleString()}/${safeTotal.toLocaleString()} words`;
};

const buildChecklistFromActiveTask = (activeTask: ProjectManifest["active_task"]): ChecklistItem[] => {
  if (!activeTask || !Array.isArray(activeTask.checklist)) {
    return [];
  }
  return activeTask.checklist
    .filter((row): row is NonNullable<typeof row> => !!row && typeof row.id === "string")
    .map((row) => {
      return {
        id: row.id,
        label: typeof row.label === "string" && row.label.trim() ? row.label : row.id,
        state: normalizeChecklistState(row.state),
        detail: typeof row.detail === "string" && row.detail.trim() ? row.detail.trim() : undefined
      };
    });
};

const formatElapsedSince = (startedAt: string | null): string => {
  if (!startedAt) {
    return "";
  }
  const startedMs = Date.parse(startedAt);
  if (!Number.isFinite(startedMs)) {
    return "";
  }
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedMs) / 1000));
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds % 60;
  return `Elapsed ${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
};

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

export const OUTLINE_AUTO_SENTINEL = "auto";

function resolveOutlineColor(outlineColor: string, textColor: string): string {
  if (outlineColor !== OUTLINE_AUTO_SENTINEL) {
    return outlineColor;
  }
  if (!HEX_COLOR_PATTERN.test(textColor)) {
    return "#000000";
  }
  const r = Number.parseInt(textColor.slice(1, 3), 16) / 255;
  const g = Number.parseInt(textColor.slice(3, 5), 16) / 255;
  const b = Number.parseInt(textColor.slice(5, 7), 16) / 255;
  const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
  return luminance > 0.5 ? "#000000" : "#FFFFFF";
}

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

const normalizePathInput = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  const quote = trimmed[0];
  const isQuoted = (quote === '"' || quote === "'") && trimmed.endsWith(quote);
  if (isQuoted) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
};

const getPathSeparator = (value: string) => (value.includes("\\") ? "\\" : "/");

const getDirName = (value: string) => {
  const normalized = normalizePathInput(value);
  if (!normalized) {
    return "";
  }
  const parts = normalized.split(/[/\\]/);
  parts.pop();
  const separator = getPathSeparator(normalized);
  const dir = parts.join(separator);
  if (/^[a-zA-Z]:$/.test(dir)) {
    return `${dir}${separator}`;
  }
  return dir;
};

const buildPathCandidates = (value: string): string[] => {
  const normalized = normalizePathInput(value);
  if (!normalized) {
    return [];
  }
  const candidates = [normalized];
  if (/^[a-zA-Z]:\\/.test(normalized)) {
    candidates.push(normalized.replace(/\\/g, "/"));
  } else if (/^[a-zA-Z]:\//.test(normalized)) {
    candidates.push(normalized.replace(/\//g, "\\"));
  }
  return [...new Set(candidates)];
};

const describeOpenError = (error: unknown): string => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  if (error && typeof error === "object") {
    const details = error as Record<string, unknown>;
    const messageKeys = ["message", "error", "reason", "details"];
    for (const key of messageKeys) {
      const value = details[key];
      if (typeof value === "string" && value.trim()) {
        return value;
      }
    }
    try {
      const serialized = JSON.stringify(error);
      if (serialized && serialized !== "{}") {
        return serialized;
      }
    } catch {
      // Ignore serialization errors and use generic fallback.
    }
  }
  return "No additional error details were provided.";
};

type ProjectWordTimingCue = ProjectWordTimingsDocument["cues"][number];

const resolveHighlightWordIndexFromTimings = (
  cue: SrtCue,
  currentTimeSeconds: number,
  cueTiming: ProjectWordTimingCue | undefined
): number | null => {
  if (!cueTiming || !Array.isArray(cueTiming.words) || cueTiming.words.length === 0) {
    return null;
  }

  const cueDuration = Math.max(0, cue.endSeconds - cue.startSeconds);
  const rawSpans = cueTiming.words
    .map((word) => {
      if (
        typeof word.start !== "number" ||
        !Number.isFinite(word.start) ||
        typeof word.end !== "number" ||
        !Number.isFinite(word.end)
      ) {
        return null;
      }
      return { startSeconds: word.start, endSeconds: word.end };
    })
    .filter(
      (entry): entry is { startSeconds: number; endSeconds: number } => entry !== null
    );

  if (rawSpans.length === 0) {
    return null;
  }

  // Alignment artifacts are normally absolute timeline seconds. Some artifacts can be cue-relative.
  const looksCueRelative = rawSpans.every(
    ({ startSeconds, endSeconds }) =>
      startSeconds >= -0.25 && endSeconds <= cueDuration + 0.25 && endSeconds >= startSeconds
  );

  const entries = rawSpans
    .map(({ startSeconds, endSeconds }) => {
      const resolvedStart = looksCueRelative ? cue.startSeconds + startSeconds : startSeconds;
      const resolvedEnd = looksCueRelative ? cue.startSeconds + endSeconds : endSeconds;
      const clampedStart = Math.max(cue.startSeconds, resolvedStart);
      const clampedEnd = Math.min(cue.endSeconds, resolvedEnd);
      const start = clampedStart;
      const end = clampedEnd;
      if (endSeconds <= startSeconds) {
        return null;
      }
      return { startSeconds: start, endSeconds: end };
    })
    .filter(
      (entry): entry is { startSeconds: number; endSeconds: number } =>
        entry !== null && entry.endSeconds > entry.startSeconds
    )
    .sort((a, b) =>
      a.startSeconds === b.startSeconds ? a.endSeconds - b.endSeconds : a.startSeconds - b.startSeconds
    );

  if (entries.length === 0) {
    return null;
  }

  const cueWordCount = (cue.text.match(/\S+/g) ?? []).length;
  if (cueWordCount <= 0) {
    return null;
  }

  if (currentTimeSeconds < entries[0].startSeconds) {
    return null;
  }

  let activeTimingRank = 0;
  for (let idx = 1; idx < entries.length; idx += 1) {
    if (currentTimeSeconds >= entries[idx].startSeconds) {
      activeTimingRank = idx;
    } else {
      break;
    }
  }
  return Math.min(activeTimingRank, cueWordCount - 1);
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

const Workbench = ({ projectId: projectIdProp }: WorkbenchProps = {}) => {
  const location = useLocation();
  const incomingState = location.state as WorkbenchLocationState;
  const navigate = useNavigate();
  const paramsProjectId = useParams().projectId;
  const projectId = projectIdProp ?? paramsProjectId ?? undefined;
  const { pushToast, markExportCompleteSeen, haveExportCompleteBeenSeen } = useToast();
  const { tabs, ensureTab, updateTabMeta } = useWorkbenchTabs();
  const width = useWindowWidth();
  const height = useWindowHeight();
  const isNarrow = width < 1100;
  const isShortWindow = height < 600;
  const isTauriEnv = isTauri();
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const activeSubtitleRef = React.useRef<HTMLTextAreaElement | null>(null);
  const subtitleOverlayPositionLayerRef = React.useRef<HTMLDivElement | null>(null);
  const activeSubtitleWrapperRef = React.useRef<HTMLDivElement | null>(null);
  const subtitleEditorControlsRef = React.useRef<HTMLDivElement | null>(null);
  const videoControlsBarRef = React.useRef<HTMLDivElement | null>(null);
  const videoWrapperRef = React.useRef<HTMLDivElement | null>(null);
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
  const [preset, setPreset] = React.useState<string>("classic_static");
  const [lastPresetId, setLastPresetId] = React.useState<string | null>(null);
  const [highlightOpacity, setHighlightOpacity] = React.useState(1.0);
  const [currentTimeSeconds, setCurrentTimeSeconds] = React.useState(0);
  const [durationSeconds, setDurationSeconds] = React.useState(0);
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [playPauseFeedback, setPlayPauseFeedback] = React.useState<"play" | "pause" | null>(null);
  const [playPauseFeedbackVisible, setPlayPauseFeedbackVisible] = React.useState(false);
  const playPauseFeedbackTimeoutsRef = React.useRef<ReturnType<typeof setTimeout>[]>([]);
  const [volume, setVolume] = React.useState(1);
  const [isMuted, setIsMuted] = React.useState(false);
  const [videoNaturalSize, setVideoNaturalSize] = React.useState({ width: 0, height: 0 });
  const [displayedVideoRect, setDisplayedVideoRect] = React.useState({
    width: 0,
    height: 0,
    offsetX: 0,
    offsetY: 0,
    scale: 1
  });
  const [subtitleOverlayPath, setSubtitleOverlayPath] = React.useState<string | null>(null);
  const [cues, setCues] = React.useState<SrtCue[]>([]);
  const [wordTimingsDoc, setWordTimingsDoc] = React.useState<ProjectWordTimingsDocument | null>(
    null
  );
  const [selectedCueId, setSelectedCueId] = React.useState<string | null>(null);
  const [editingCueId, setEditingCueId] = React.useState<string | null>(null);
  const [editingText, setEditingText] = React.useState("");
  const [subtitleEditorControlsPlacement, setSubtitleEditorControlsPlacement] =
    React.useState<"above" | "below">("below");
  const [canUndoEdit, setCanUndoEdit] = React.useState(false);
  const [isSavingCue, setIsSavingCue] = React.useState(false);
  const [leftPanelOpen, setLeftPanelOpen] = React.useState(false);
  const [rightOverlayOpen, setRightOverlayOpen] = React.useState(false);
  const [showVideoControls, setShowVideoControls] = React.useState(false);
  const [isHoveringActiveSubtitle, setIsHoveringActiveSubtitle] = React.useState(false);
  const [progressHoverSeconds, setProgressHoverSeconds] = React.useState<number | null>(null);
  const [progressHoverXPx, setProgressHoverXPx] = React.useState<number | null>(null);
  const lastProgressHoverXPxRef = React.useRef<number>(0);
  const [playbackSpeed, setPlaybackSpeed] = React.useState(() => {
    if (typeof window === "undefined") return 1;
    const stored = window.localStorage.getItem("workbench_playback_speed");
    if (stored == null) return 1;
    const parsed = Number.parseFloat(stored);
    return Number.isFinite(parsed) && parsed >= 0.25 && parsed <= 2 ? parsed : 1;
  });
  const [speedPopoverOpen, setSpeedPopoverOpen] = React.useState(false);
  const speedPopoverOpenDelayRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const speedPopoverCloseTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const speedControlClickRef = React.useRef(false);
  const SPEED_POPOVER_CLOSE_DELAY_MS = 200;
  const [seekFeedback, setSeekFeedback] = React.useState<{ text: string; side: "left" | "right" } | null>(
    null
  );
  const seekFeedbackTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const [subtitleControlsPushPx, setSubtitleControlsPushPx] = React.useState(0);
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
  const [, setCreateSubtitlesJobStream] = React.useState<JobEventStream | null>(null);
  const createSubtitlesJobStreamRef = React.useRef<JobEventStream | null>(null);
  const [createSubtitlesStreamHealth, setCreateSubtitlesStreamHealth] =
    React.useState<StreamHealth>("idle");
  const createSubtitlesStreamHealthRef = React.useRef<StreamHealth>("idle");
  const createSubtitlesStreamCooldownUntilRef = React.useRef(0);
  const createSubtitlesStreamCooldownTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const latestCreateLiveEventAtMsRef = React.useRef(0);
  const createSubtitlesJobIdRef = React.useRef<string | null>(null);
  const createSubtitlesJustStartedRef = React.useRef(false);
  const projectIdRef = React.useRef<string | null>(null);
  projectIdRef.current = projectId ?? null;
  const [createSubtitlesStartedAt, setCreateSubtitlesStartedAt] = React.useState<string | null>(
    null
  );
  const [createSubtitlesElapsedText, setCreateSubtitlesElapsedText] = React.useState("");
  const [showElevatorMusicRow, setShowElevatorMusicRow] = React.useState(false);
  const [elevatorMusicPlaying, setElevatorMusicPlaying] = React.useState(false);
  const elevatorMusicTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const elevatorMusicRowScheduledRef = React.useRef(false);
  const elevatorAudioRef = React.useRef<HTMLAudioElement | null>(null);
  const selectedElevatorTrackIndexRef = React.useRef<number | null>(null);
  const preparingPreviewStartedAtRef = React.useRef<number | null>(null);
  const preparingPreviewDelayTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const preparingPreviewDoneTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const preparingPreviewCompletionScheduledRef = React.useRef(false);
  const [isExporting, setIsExporting] = React.useState(false);
  const [exportError, setExportError] = React.useState<string | null>(null);
  const [exportHeading, setExportHeading] = React.useState("Exporting video");
  const [exportProgressPct, setExportProgressPct] = React.useState(0);
  const [exportProgressMessage, setExportProgressMessage] = React.useState<string>("");
  const [exportChecklist, setExportChecklist] = React.useState<ChecklistItem[]>([]);
  const [, setExportJobStream] = React.useState<JobEventStream | null>(null);
  const exportJobStreamRef = React.useRef<JobEventStream | null>(null);
  const [exportStreamHealth, setExportStreamHealth] = React.useState<StreamHealth>("idle");
  const exportStreamHealthRef = React.useRef<StreamHealth>("idle");
  const exportStreamCooldownUntilRef = React.useRef(0);
  const exportStreamCooldownTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestExportLiveEventAtMsRef = React.useRef(0);
  const exportJobIdRef = React.useRef<string | null>(null);
  const { registerJob: registerRunningJob } = useRunningJobs();
  const createSubtitlesUnregisterRef = React.useRef<(() => void) | null>(null);
  const exportUnregisterRef = React.useRef<(() => void) | null>(null);
  const [exportStartedAt, setExportStartedAt] = React.useState<string | null>(null);
  const [exportElapsedText, setExportElapsedText] = React.useState("");
  const [exportOutputPath, setExportOutputPath] = React.useState<string | null>(null);
  const [openActionError, setOpenActionError] = React.useState<string | null>(null);
  const [projectReloadTick, setProjectReloadTick] = React.useState(0);
  const [subtitlesReloadTick, setSubtitlesReloadTick] = React.useState(0);
  const projectFetchSeqRef = React.useRef(0);
  const knownTimingWordsTotalRef = React.useRef<number | null>(null);
  const latestTimingAuthoritativeAtMsRef = React.useRef(0);
  const [timingFallbackDetail, setTimingFallbackDetail] = React.useState<string | null>(null);
  const timingFallbackProgressRef = React.useRef<TimingFallbackProgress | null>(null);
  const [pendingAutoStartSubtitles, setPendingAutoStartSubtitles] = React.useState(false);
  const handledAutoStartKeyRef = React.useRef<string | null>(null);
  const styleBootstrapKeyRef = React.useRef<string | null>(null);
  const overlayRequestKeyRef = React.useRef<string | null>(null);
  const showSubtitlesOverlay = false;

  const setCreateStreamHealthValue = React.useCallback((next: StreamHealth) => {
    createSubtitlesStreamHealthRef.current = next;
    setCreateSubtitlesStreamHealth(next);
  }, []);

  const setExportStreamHealthValue = React.useCallback((next: StreamHealth) => {
    exportStreamHealthRef.current = next;
    setExportStreamHealth(next);
  }, []);

  const noteCreateLiveEventTimestamp = React.useCallback((event: JobEvent) => {
    const eventMs = parseIsoTimestampMs(event.ts);
    if (eventMs > latestCreateLiveEventAtMsRef.current) {
      latestCreateLiveEventAtMsRef.current = eventMs;
    }
  }, []);

  const noteExportLiveEventTimestamp = React.useCallback((event: JobEvent) => {
    const eventMs = parseIsoTimestampMs(event.ts);
    if (eventMs > latestExportLiveEventAtMsRef.current) {
      latestExportLiveEventAtMsRef.current = eventMs;
    }
  }, []);

  const rememberTimingAuthoritativeDetail = React.useCallback(
    (detail: string | null | undefined, eventTs?: string | null) => {
      const parsed = parseAlignmentWordDetail(detail);
      if (!parsed) {
        return;
      }
      knownTimingWordsTotalRef.current = parsed.total;
      const fallback = timingFallbackProgressRef.current;
      if (fallback && fallback.total === parsed.total) {
        // Keep showing inferred fallback progress when the polled checklist detail is behind.
        if (parsed.current < fallback.current) {
          return;
        }
        timingFallbackProgressRef.current = null;
        setTimingFallbackDetail(null);
      }
      const detailTs = parseIsoTimestampMs(eventTs);
      if (detailTs > latestTimingAuthoritativeAtMsRef.current) {
        latestTimingAuthoritativeAtMsRef.current = detailTs;
      }
    },
    []
  );

  const clearTimingFallbackProgress = React.useCallback(() => {
    timingFallbackProgressRef.current = null;
    setTimingFallbackDetail(null);
  }, []);

  const withTimingFallbackChecklist = React.useCallback(
    (items: ChecklistItem[]): ChecklistItem[] => {
      const fallback = timingFallbackProgressRef.current;
      if (!fallback) {
        return items;
      }
      if (fallback.updatedAtMs <= latestTimingAuthoritativeAtMsRef.current) {
        return items;
      }
      const fallbackDetail = timingFallbackDetail;
      if (!fallbackDetail) {
        return items;
      }
      return items.map((item) => {
        if (item.id !== checklistStepIds.timingWordHighlights || item.state !== "active") {
          return item;
        }
        const authoritative = parseAlignmentWordDetail(item.detail);
        if (!authoritative) {
          return { ...item, detail: fallbackDetail };
        }
        if (authoritative.total !== fallback.total) {
          return item;
        }
        if (authoritative.current >= fallback.current) {
          return item;
        }
        return { ...item, detail: fallbackDetail };
      });
    },
    [timingFallbackDetail]
  );

  React.useEffect(() => {
    return () => {
      createSubtitlesUnregisterRef.current?.();
      createSubtitlesUnregisterRef.current = null;
      exportUnregisterRef.current?.();
      exportUnregisterRef.current = null;
      if (createSubtitlesStreamCooldownTimerRef.current !== null) {
        clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
        createSubtitlesStreamCooldownTimerRef.current = null;
      }
      if (exportStreamCooldownTimerRef.current !== null) {
        clearTimeout(exportStreamCooldownTimerRef.current);
        exportStreamCooldownTimerRef.current = null;
      }
      createSubtitlesJobStreamRef.current?.close();
      createSubtitlesJobStreamRef.current = null;
      exportJobStreamRef.current?.close();
      exportJobStreamRef.current = null;
      if (preparingPreviewDelayTimerRef.current !== null) {
        clearTimeout(preparingPreviewDelayTimerRef.current);
        preparingPreviewDelayTimerRef.current = null;
      }
      if (preparingPreviewDoneTimerRef.current !== null) {
        clearTimeout(preparingPreviewDoneTimerRef.current);
        preparingPreviewDoneTimerRef.current = null;
      }
      preparingPreviewCompletionScheduledRef.current = false;
      preparingPreviewStartedAtRef.current = null;
      playPauseFeedbackTimeoutsRef.current.forEach(clearTimeout);
      playPauseFeedbackTimeoutsRef.current = [];
    };
  }, []);

  React.useEffect(() => {
    let active = true;
    if (!projectId) {
      setError("Missing video id.");
      setIsLoading(false);
      return () => {
        active = false;
      };
    }
    const fetchSeq = projectFetchSeqRef.current + 1;
    projectFetchSeqRef.current = fetchSeq;
    setIsLoading((prev) => (project?.project_id === projectId && prev === false ? false : true));
    fetchProject(projectId)
      .then((data) => {
        if (!active || fetchSeq !== projectFetchSeqRef.current) return;
        setProject(data);
        setExportOutputPath(data.latest_export?.output_video_path ?? null);
        setError(null);
      })
      .catch((err) => {
        if (!active || fetchSeq !== projectFetchSeqRef.current) return;
        setError(messageForBackendError(err, err instanceof Error ? err.message : "Failed to load video."));
      })
      .finally(() => {
        if (!active || fetchSeq !== projectFetchSeqRef.current) return;
        setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [project?.project_id, projectId, projectReloadTick]);

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
        setSubtitleLoadError(messageForBackendError(err, message));
      });

    return () => {
      active = false;
    };
  }, [projectId, subtitlesReloadTick]);

  React.useEffect(() => {
    let active = true;
    if (!projectId) {
      setWordTimingsDoc(null);
      return () => {
        active = false;
      };
    }

    setWordTimingsDoc(null);
    fetchProjectWordTimings(projectId)
      .then((payload) => {
        if (!active) {
          return;
        }
        if (payload.available && payload.document && payload.stale === false) {
          setWordTimingsDoc(payload.document);
          return;
        }
        setWordTimingsDoc(null);
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setWordTimingsDoc(null);
      });

    return () => {
      active = false;
    };
  }, [projectId, subtitlesReloadTick]);

  const LEGACY_PRESET_MAP: Record<string, string> = {
    Default: "classic_static",
    "Large outline": "bold_outline_static",
    "Large outline + box": "boxed_static",
    Lift: "lift_static"
  };

  const PRESET_ID_TO_BACKEND_NAME: Record<string, string> = {
    classic_static: "Default",
    bold_outline_static: "Large outline",
    boxed_static: "Large outline + box",
    lift_static: "Lift",
    neon_karaoke: "Default",
    boxed_karaoke: "Default"
  };

  const resolvePresetFromStored = (stored: string | undefined): string =>
    LEGACY_PRESET_MAP[stored ?? ""] ?? stored ?? "classic_static";

  const applyStyleFromSettings = React.useCallback((data: SettingsConfig) => {
    const style = data.subtitle_style;
    const app = (style.appearance as SubtitleStyleAppearance | undefined) ?? DEFAULT_APPEARANCE;
    const resolvedAppearance = migrateAppearancePadding({
      ...DEFAULT_APPEARANCE,
      ...app,
      subtitle_mode: data.subtitle_mode ?? app.subtitle_mode,
      highlight_color: style.highlight_color ?? app.highlight_color
    });
    const storedPreset = style.preset ?? "Default";
    const resolvedPreset = resolvePresetFromStored(storedPreset);
    const storedLastPresetId =
      typeof (style as Record<string, unknown>).last_preset_id === "string"
        ? (style as Record<string, unknown>).last_preset_id as string
        : undefined;
    setAppearance(resolvedAppearance);
    setPreset(resolvedPreset);
    setLastPresetId(
      isNamedPresetId(resolvedPreset)
        ? resolvedPreset
        : storedLastPresetId && isNamedPresetId(storedLastPresetId)
          ? storedLastPresetId
          : null
    );
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
    const resolvedAppearance = migrateAppearancePadding({
      ...DEFAULT_APPEARANCE,
      ...(rawAppearance as unknown as SubtitleStyleAppearance),
      subtitle_mode: styleMode ?? DEFAULT_APPEARANCE.subtitle_mode,
      highlight_color: highlightColor ?? DEFAULT_APPEARANCE.highlight_color
    });
    const storedPreset =
      typeof styleSection.preset === "string" ? styleSection.preset : "Default";
    const resolvedPreset = resolvePresetFromStored(storedPreset);
    const storedLastPresetId =
      typeof styleSection.last_preset_id === "string"
        ? styleSection.last_preset_id
        : undefined;
    const resolvedOpacity =
      typeof styleSection.highlight_opacity === "number"
        ? styleSection.highlight_opacity
        : 1.0;
    setAppearance(resolvedAppearance);
    setPreset(resolvedPreset);
    setLastPresetId(
      isNamedPresetId(resolvedPreset)
        ? resolvedPreset
        : storedLastPresetId && isNamedPresetId(storedLastPresetId)
          ? storedLastPresetId
          : null
    );
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
      nextHighlightOpacity: number,
      lastPresetIdValue: string | null
    ) => ({
      subtitle_mode: nextAppearance.subtitle_mode,
      subtitle_style: {
        preset: PRESET_ID_TO_BACKEND_NAME[nextPreset] ?? nextPreset,
        last_preset_id: lastPresetIdValue ?? undefined,
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
        setStyleError(messageForBackendError(err, err instanceof Error ? err.message : "Failed to load style settings."));
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
    const storedPreset = settings.subtitle_style?.preset ?? "Default";
    const resolvedPreset = resolvePresetFromStored(storedPreset);
    const storedLast =
      typeof (settings.subtitle_style as Record<string, unknown> | undefined)
        ?.last_preset_id === "string"
        ? (settings.subtitle_style as Record<string, unknown>).last_preset_id as string
        : null;
    const fallbackPayload = buildProjectStylePayload(
      {
        ...DEFAULT_APPEARANCE,
        ...(settings.subtitle_style?.appearance as SubtitleStyleAppearance | undefined),
        subtitle_mode: settings.subtitle_mode ?? DEFAULT_APPEARANCE.subtitle_mode,
        highlight_color:
          settings.subtitle_style?.highlight_color ?? DEFAULT_APPEARANCE.highlight_color
      },
      resolvedPreset,
      settings.subtitle_style?.highlight_opacity ?? 1.0,
      storedLast
    );
    void updateProject(projectId, { style: fallbackPayload })
      .then(() => {
        setStyleError(null);
        setProjectReloadTick((prev) => prev + 1);
      })
      .catch((err) => {
        setStyleError(
          messageForBackendError(err, err instanceof Error ? err.message : "Failed to save video style settings.")
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
    if (preparingPreviewDelayTimerRef.current !== null) {
      clearTimeout(preparingPreviewDelayTimerRef.current);
      preparingPreviewDelayTimerRef.current = null;
    }
    if (preparingPreviewDoneTimerRef.current !== null) {
      clearTimeout(preparingPreviewDoneTimerRef.current);
      preparingPreviewDoneTimerRef.current = null;
    }
    preparingPreviewCompletionScheduledRef.current = false;
    preparingPreviewStartedAtRef.current = null;
    setIsCreatingSubtitles(false);
    setCreateSubtitlesStartedAt(null);
    createSubtitlesJobIdRef.current = null;
    latestCreateLiveEventAtMsRef.current = 0;
    knownTimingWordsTotalRef.current = null;
    latestTimingAuthoritativeAtMsRef.current = 0;
    clearTimingFallbackProgress();
    if (createSubtitlesStreamCooldownTimerRef.current !== null) {
      clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
      createSubtitlesStreamCooldownTimerRef.current = null;
    }
    createSubtitlesStreamCooldownUntilRef.current = 0;
    createSubtitlesJobStreamRef.current?.close();
    createSubtitlesJobStreamRef.current = null;
    setCreateSubtitlesJobStream(null);
    setCreateStreamHealthValue("idle");
    setExportError(null);
    setOpenActionError(null);
    setExportHeading("Exporting video");
    setExportProgressPct(0);
    setExportProgressMessage("");
    setExportChecklist([]);
    setIsExporting(false);
    setExportStartedAt(null);
    exportJobIdRef.current = null;
    latestExportLiveEventAtMsRef.current = 0;
    if (exportStreamCooldownTimerRef.current !== null) {
      clearTimeout(exportStreamCooldownTimerRef.current);
      exportStreamCooldownTimerRef.current = null;
    }
    exportStreamCooldownUntilRef.current = 0;
    exportJobStreamRef.current?.close();
    exportJobStreamRef.current = null;
    setExportJobStream(null);
    setExportStreamHealthValue("idle");
    setExportOutputPath(null);
    setSubtitleOverlayPath(null);
    setVideoNaturalSize({ width: 0, height: 0 });
    setDurationSeconds(0);
    setIsPlaying(false);
    overlayRequestKeyRef.current = null;
    setCanUndoEdit(false);
    editHistoryRef.current = [];
    editHistoryIndexRef.current = 0;
    lastHistoryCommitAtRef.current = 0;
    shouldResumePlaybackRef.current = false;
  }, [clearTimingFallbackProgress, projectId, setCreateStreamHealthValue, setExportStreamHealthValue]);

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
    const title = resolveTitle(project);
    const rawPath = project?.video?.path ?? project?.video?.filename ?? "";
    const path =
      rawPath && (rawPath.includes("/") || rawPath.includes("\\")) ? rawPath : undefined;
    updateTabMeta(projectId, {
      title,
      ...(path && { path }),
      thumbnail_path: project?.video?.thumbnail_path ?? undefined
    });
  }, [project, projectId, updateTabMeta]);

  React.useEffect(() => {
    if (!isNarrow) {
      setRightOverlayOpen(false);
    }
  }, [isNarrow]);

  React.useEffect(() => {
    if (!isCreatingSubtitles || !createSubtitlesStartedAt) {
      setCreateSubtitlesElapsedText("");
      return;
    }
    const tick = () => {
      setCreateSubtitlesElapsedText(formatElapsedSince(createSubtitlesStartedAt));
    };
    tick();
    const timer = window.setInterval(tick, 500);
    return () => {
      clearInterval(timer);
    };
  }, [createSubtitlesStartedAt, isCreatingSubtitles]);

  React.useEffect(() => {
    if (!createSubtitlesStartedAt || !isCreatingSubtitles || elevatorMusicRowScheduledRef.current) {
      return;
    }
    elevatorMusicRowScheduledRef.current = true;
    elevatorMusicTimerRef.current = window.setTimeout(() => {
      elevatorMusicTimerRef.current = null;
      setShowElevatorMusicRow(true);
    }, 10_000);
    return () => {
      if (elevatorMusicTimerRef.current !== null) {
        clearTimeout(elevatorMusicTimerRef.current);
        elevatorMusicTimerRef.current = null;
      }
    };
  }, [createSubtitlesStartedAt, isCreatingSubtitles]);

  React.useEffect(() => {
    if (createSubtitlesStartedAt !== null) {
      return;
    }
    elevatorMusicRowScheduledRef.current = false;
    setShowElevatorMusicRow(false);
    setElevatorMusicPlaying(false);
    selectedElevatorTrackIndexRef.current = null;
    elevatorAudioRef.current?.pause();
  }, [createSubtitlesStartedAt]);

  React.useEffect(() => {
    if (!isExporting || !exportStartedAt) {
      setExportElapsedText("");
      return;
    }
    const tick = () => {
      setExportElapsedText(formatElapsedSince(exportStartedAt));
    };
    tick();
    const timer = window.setInterval(tick, 500);
    return () => {
      clearInterval(timer);
    };
  }, [exportStartedAt, isExporting]);

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
      const selected = await openDialog({
        directory: true,
        multiple: false,
        title: "Choose folder to save subtitles"
      });
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
    const reasonText = asNonEmptyString(event.reason_text);
    if (reasonText) {
      return reasonText;
    }
    const reasonCode = asString(event.reason_code);
    if (event.step_id === checklistStepIds.fixMissingSubtitles && reasonCode) {
      return MISSING_SUBTITLES_REASON_TEXT[reasonCode];
    }
    if (event.step_id === checklistStepIds.timingWordHighlights && reasonCode) {
      return WORD_HIGHLIGHT_REASON_TEXT[reasonCode];
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

  const clearPreparingPreviewTimers = React.useCallback(() => {
    if (preparingPreviewDelayTimerRef.current !== null) {
      clearTimeout(preparingPreviewDelayTimerRef.current);
      preparingPreviewDelayTimerRef.current = null;
    }
    if (preparingPreviewDoneTimerRef.current !== null) {
      clearTimeout(preparingPreviewDoneTimerRef.current);
      preparingPreviewDoneTimerRef.current = null;
    }
    preparingPreviewCompletionScheduledRef.current = false;
  }, []);

  const closeCreateSubtitlesStream = React.useCallback(
    (reason: string) => {
      void reason;
      const current = createSubtitlesJobStreamRef.current;
      if (current) {
        current.close();
      }
      createSubtitlesJobStreamRef.current = null;
      setCreateSubtitlesJobStream(null);
      if (createSubtitlesStreamHealthRef.current !== "cooldown") {
        setCreateStreamHealthValue("idle");
      }
    },
    [setCreateStreamHealthValue]
  );

  const closeExportStream = React.useCallback(
    (reason: string) => {
      void reason;
      const current = exportJobStreamRef.current;
      if (current) {
        current.close();
      }
      exportJobStreamRef.current = null;
      setExportJobStream(null);
      if (exportStreamHealthRef.current !== "cooldown") {
        setExportStreamHealthValue("idle");
      }
    },
    [setExportStreamHealthValue]
  );

  const startCreateStreamCooldown = React.useCallback(() => {
    const cooldownUntil = Date.now() + STREAM_ATTACH_COOLDOWN_MS;
    createSubtitlesStreamCooldownUntilRef.current = cooldownUntil;
    if (createSubtitlesStreamCooldownTimerRef.current !== null) {
      clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
    }
    setCreateStreamHealthValue("cooldown");
    createSubtitlesStreamCooldownTimerRef.current = setTimeout(() => {
      createSubtitlesStreamCooldownTimerRef.current = null;
      if (
        createSubtitlesStreamHealthRef.current === "cooldown" &&
        Date.now() >= createSubtitlesStreamCooldownUntilRef.current
      ) {
        createSubtitlesStreamCooldownUntilRef.current = 0;
        setCreateStreamHealthValue("idle");
        setProjectReloadTick((prev) => prev + 1);
      }
    }, STREAM_ATTACH_COOLDOWN_MS);
  }, [setCreateStreamHealthValue]);

  const startExportStreamCooldown = React.useCallback(() => {
    const cooldownUntil = Date.now() + STREAM_ATTACH_COOLDOWN_MS;
    exportStreamCooldownUntilRef.current = cooldownUntil;
    if (exportStreamCooldownTimerRef.current !== null) {
      clearTimeout(exportStreamCooldownTimerRef.current);
    }
    setExportStreamHealthValue("cooldown");
    exportStreamCooldownTimerRef.current = setTimeout(() => {
      exportStreamCooldownTimerRef.current = null;
      if (
        exportStreamHealthRef.current === "cooldown" &&
        Date.now() >= exportStreamCooldownUntilRef.current
      ) {
        exportStreamCooldownUntilRef.current = 0;
        setExportStreamHealthValue("idle");
        setProjectReloadTick((prev) => prev + 1);
      }
    }, STREAM_ATTACH_COOLDOWN_MS);
  }, [setExportStreamHealthValue]);

  const finalizeCreateSubtitlesCompleted = React.useCallback(() => {
    clearPreparingPreviewTimers();
    preparingPreviewStartedAtRef.current = null;
    createSubtitlesUnregisterRef.current?.();
    createSubtitlesUnregisterRef.current = null;
    if (projectIdRef.current) clearPersistedRunningJob(projectIdRef.current);
    setCreateSubtitlesProgressPct(100);
    setIsCreatingSubtitles(false);
    setCreateSubtitlesStartedAt(null);
    createSubtitlesJobIdRef.current = null;
    if (createSubtitlesStreamCooldownTimerRef.current !== null) {
      clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
      createSubtitlesStreamCooldownTimerRef.current = null;
    }
    createSubtitlesStreamCooldownUntilRef.current = 0;
    closeCreateSubtitlesStream("create_subtitles_completed");
    setCreateStreamHealthValue("idle");
    clearTimingFallbackProgress();
    setProjectReloadTick((prev) => prev + 1);
    setSubtitlesReloadTick((prev) => prev + 1);
  }, [clearPreparingPreviewTimers, clearTimingFallbackProgress, closeCreateSubtitlesStream, setCreateStreamHealthValue]);

  const scheduleCreateSubtitlesCompletion = React.useCallback(() => {
    if (preparingPreviewCompletionScheduledRef.current) {
      return;
    }
    preparingPreviewCompletionScheduledRef.current = true;
    setIsCreatingSubtitles(false);
    const startedAtMs = preparingPreviewStartedAtRef.current;
    const elapsedMs = startedAtMs != null ? Date.now() - startedAtMs : PREPARING_PREVIEW_MIN_ACTIVE_MS;
    const remainingActiveMs = Math.max(0, PREPARING_PREVIEW_MIN_ACTIVE_MS - elapsedMs);
    const finalize = () => {
      updateCreateChecklist(checklistStepIds.preparingPreview, "done");
      preparingPreviewDoneTimerRef.current = setTimeout(() => {
        preparingPreviewDoneTimerRef.current = null;
        finalizeCreateSubtitlesCompleted();
      }, PREPARING_PREVIEW_DONE_VISIBLE_MS);
    };
    if (remainingActiveMs > 0) {
      preparingPreviewDelayTimerRef.current = setTimeout(() => {
        preparingPreviewDelayTimerRef.current = null;
        finalize();
      }, remainingActiveMs);
      return;
    }
    finalize();
  }, [finalizeCreateSubtitlesCompleted, updateCreateChecklist]);

  const handleCreateSubtitlesEvent = React.useCallback(
    (event: JobEvent) => {
      noteCreateLiveEventTimestamp(event);
      if (event.type === "started") {
        setCreateSubtitlesHeading(asNonEmptyString(event.heading) ?? "Creating subtitles");
        setCreateSubtitlesStartedAt((prev) => {
          const ts = asString(event.ts) ?? new Date().toISOString();
          if (!prev) return ts;
          const prevMs = Date.parse(prev);
          const tsMs = Date.parse(ts);
          if (!Number.isFinite(prevMs) || !Number.isFinite(tsMs)) return prev ?? ts;
          return prevMs <= tsMs ? prev : ts;
        });
        return;
      }
      if (event.type === "checklist") {
        const stepId = asString(event.step_id);
        const state = asString(event.state);
        if (!stepId || !state) {
          return;
        }
        const checklistReason = resolveChecklistReason(event);
        if (stepId === checklistStepIds.timingWordHighlights) {
          rememberTimingAuthoritativeDetail(checklistReason, asString(event.ts));
          if (state !== "start") {
            clearTimingFallbackProgress();
          }
        }
        if (stepId === checklistStepIds.preparingPreview && state === "start") {
          clearPreparingPreviewTimers();
          preparingPreviewStartedAtRef.current = Date.now();
        }
        if (stepId === checklistStepIds.preparingPreview && state === "done") {
          const startedAtMs = preparingPreviewStartedAtRef.current;
          if (
            startedAtMs != null &&
            Date.now() - startedAtMs < PREPARING_PREVIEW_MIN_ACTIVE_MS
          ) {
            return;
          }
        }
        updateCreateChecklist(stepId, state, checklistReason);
        return;
      }
      if (event.type === "progress") {
        if (typeof event.pct === "number") {
          setCreateSubtitlesProgressPct(event.pct);
        }
        const stepId = asString(event.step_id);
        if (
          stepId &&
          ALIGNMENT_PROGRESS_STEP_IDS.has(stepId) &&
          typeof event.step_progress === "number" &&
          Number.isFinite(event.step_progress)
        ) {
          const total = knownTimingWordsTotalRef.current;
          if (total && total > 0) {
            const progress = Math.max(0, Math.min(1, event.step_progress));
            const current = Math.max(0, Math.min(total, Math.round(progress * total)));
            const fallback = timingFallbackProgressRef.current;
            const fallbackCurrent =
              fallback && fallback.total === total ? fallback.current : -1;
            if (current > fallbackCurrent) {
              const detail = formatAlignmentWordDetail(current, total);
              timingFallbackProgressRef.current = {
                current,
                total,
                updatedAtMs: Date.now()
              };
              setTimingFallbackDetail(detail);
            }
          }
        }
        const message = asString(event.message);
        if (message) {
          setCreateSubtitlesProgressMessage(message);
        }
        return;
      }
      if (event.type === "result") {
        return;
      }
      if (event.type === "completed") {
        scheduleCreateSubtitlesCompletion();
        return;
      }
      if (event.type === "cancelled") {
        clearPreparingPreviewTimers();
        preparingPreviewStartedAtRef.current = null;
        createSubtitlesUnregisterRef.current?.();
        createSubtitlesUnregisterRef.current = null;
        if (projectIdRef.current) clearPersistedRunningJob(projectIdRef.current);
        setCreateSubtitlesProgressPct(0);
        setCreateSubtitlesProgressMessage("");
        setIsCreatingSubtitles(false);
        setCreateSubtitlesStartedAt(null);
        createSubtitlesJobIdRef.current = null;
        clearTimingFallbackProgress();
        if (createSubtitlesStreamCooldownTimerRef.current !== null) {
          clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
          createSubtitlesStreamCooldownTimerRef.current = null;
        }
        createSubtitlesStreamCooldownUntilRef.current = 0;
        closeCreateSubtitlesStream("create_subtitles_cancelled");
        setCreateStreamHealthValue("idle");
        const message = asNonEmptyString(event.message);
        if (message) {
          setCreateSubtitlesError(normalizeCreateSubtitlesErrorMessage(message));
        }
        return;
      }
      if (event.type === "error") {
        clearPreparingPreviewTimers();
        preparingPreviewStartedAtRef.current = null;
        createSubtitlesUnregisterRef.current?.();
        createSubtitlesUnregisterRef.current = null;
        if (projectIdRef.current) clearPersistedRunningJob(projectIdRef.current);
        setCreateSubtitlesProgressPct(0);
        setCreateSubtitlesProgressMessage("");
        setIsCreatingSubtitles(false);
        setCreateSubtitlesStartedAt(null);
        createSubtitlesJobIdRef.current = null;
        clearTimingFallbackProgress();
        if (createSubtitlesStreamCooldownTimerRef.current !== null) {
          clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
          createSubtitlesStreamCooldownTimerRef.current = null;
        }
        createSubtitlesStreamCooldownUntilRef.current = 0;
        closeCreateSubtitlesStream("create_subtitles_error");
        setCreateStreamHealthValue("idle");
        setCreateSubtitlesError(
          normalizeCreateSubtitlesErrorMessage(asNonEmptyString(event.message)) ??
            "Subtitle generation failed."
        );
      }
    },
    [
      clearTimingFallbackProgress,
      clearPreparingPreviewTimers,
      closeCreateSubtitlesStream,
      noteCreateLiveEventTimestamp,
      rememberTimingAuthoritativeDetail,
      resolveChecklistReason,
      scheduleCreateSubtitlesCompletion,
      setCreateStreamHealthValue,
      updateCreateChecklist
    ]
  );

  const openCreateSubtitlesStream = React.useCallback(
    (jobId: string, eventsUrl?: string) => {
      if (!jobId) {
        return;
      }
      if (
        createSubtitlesStreamHealthRef.current === "cooldown" &&
        Date.now() < createSubtitlesStreamCooldownUntilRef.current
      ) {
        return;
      }
      if (
        createSubtitlesJobStreamRef.current?.jobId === jobId &&
        (createSubtitlesStreamHealthRef.current === "open" ||
          createSubtitlesStreamHealthRef.current === "connecting")
      ) {
        return;
      }
      closeCreateSubtitlesStream("open_create_subtitles_stream");
      setCreateStreamHealthValue("connecting");
      let streamOpened = false;
      const stream = attachToJobEvents(
        jobId,
        {
          onEvent: handleCreateSubtitlesEvent,
          onOpen: () => {
            if (createSubtitlesJobStreamRef.current !== stream) {
              return;
            }
            streamOpened = true;
            createSubtitlesStreamCooldownUntilRef.current = 0;
            if (createSubtitlesStreamCooldownTimerRef.current !== null) {
              clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
              createSubtitlesStreamCooldownTimerRef.current = null;
            }
            setCreateStreamHealthValue("open");
          },
          onError: () => {
            if (createSubtitlesJobStreamRef.current !== stream) {
              return;
            }
            closeCreateSubtitlesStream("create_subtitles_stream_error");
            if (!streamOpened) {
              startCreateStreamCooldown();
            }
            setProjectReloadTick((prev) => prev + 1);
          }
        },
        eventsUrl
      );
      createSubtitlesJobIdRef.current = jobId;
      createSubtitlesJobStreamRef.current = stream;
      setCreateSubtitlesJobStream(stream);
      createSubtitlesUnregisterRef.current?.();
      createSubtitlesUnregisterRef.current = registerRunningJob({
        id: jobId,
        label: `Creating subtitles for ${resolveTitle(project)}`,
        cancel: () => stream.cancel()
      });
    },
    [
      closeCreateSubtitlesStream,
      handleCreateSubtitlesEvent,
      project,
      registerRunningJob,
      setCreateStreamHealthValue,
      startCreateStreamCooldown
    ]
  );

  const startCreateSubtitles = React.useCallback(async () => {
    if (!projectId || !project?.video?.path || isCreatingSubtitles || isExporting) {
      return;
    }
    if (!settings) {
      setCreateSubtitlesError("Settings are still loading. Please try again.");
      return;
    }

    setCreateSubtitlesError(null);
    setCreateSubtitlesHeading("Creating subtitles");
    setCreateSubtitlesProgressPct(0);
    const genItems = buildGenerateChecklist(settings);
    const initialChecklist = defaultChecklist(genItems);
    if (initialChecklist.length > 0) {
      initialChecklist[0] = { ...initialChecklist[0], state: "active" };
    }
    setCreateSubtitlesProgressMessage(initialChecklist[0]?.label ?? "Preparing…");
    setCreateSubtitlesChecklist(initialChecklist);
    clearPreparingPreviewTimers();
    preparingPreviewStartedAtRef.current = null;
    clearTimingFallbackProgress();
    knownTimingWordsTotalRef.current = null;
    latestTimingAuthoritativeAtMsRef.current = 0;
    latestCreateLiveEventAtMsRef.current = 0;
    if (createSubtitlesStreamCooldownTimerRef.current !== null) {
      clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
      createSubtitlesStreamCooldownTimerRef.current = null;
    }
    createSubtitlesStreamCooldownUntilRef.current = 0;
    closeCreateSubtitlesStream("start_create_subtitles");
    setCreateStreamHealthValue("connecting");
    setIsCreatingSubtitles(true);
    setCreateSubtitlesStartedAt(new Date().toISOString());
    createSubtitlesJustStartedRef.current = true;

    const resolvedOutputDir = await resolveOutputDir(project.video.path, setCreateSubtitlesError);
    if (!resolvedOutputDir) {
      setIsCreatingSubtitles(false);
      setCreateSubtitlesStartedAt(null);
      createSubtitlesJustStartedRef.current = false;
      setCreateStreamHealthValue("idle");
      return;
    }

    setCreateSubtitlesProgressMessage(initialChecklist[0]?.label ?? "Extracting audio");
    let streamOpened = false;

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
          onOpen: () => {
            streamOpened = true;
            createSubtitlesStreamCooldownUntilRef.current = 0;
            if (createSubtitlesStreamCooldownTimerRef.current !== null) {
              clearTimeout(createSubtitlesStreamCooldownTimerRef.current);
              createSubtitlesStreamCooldownTimerRef.current = null;
            }
            setCreateStreamHealthValue("open");
          },
          onError: () => {
            closeCreateSubtitlesStream("create_subtitles_start_stream_error");
            if (!streamOpened) {
              startCreateStreamCooldown();
            }
            setCreateSubtitlesProgressMessage("Syncing progress...");
            setProjectReloadTick((prev) => prev + 1);
          }
        }
      );
      createSubtitlesJobIdRef.current = job.jobId;
      createSubtitlesJustStartedRef.current = false;
      createSubtitlesJobStreamRef.current = job;
      setCreateSubtitlesJobStream(job);
      setPersistedRunningJob(projectId, {
        jobId: job.jobId,
        eventsUrl: job.eventsUrl,
        kind: "create_subtitles"
      });
      createSubtitlesUnregisterRef.current?.();
      createSubtitlesUnregisterRef.current = registerRunningJob({
        id: job.jobId,
        label: `Creating subtitles for ${resolveTitle(project)}`,
        cancel: () => job.cancel()
      });
    } catch (err) {
      createSubtitlesJustStartedRef.current = false;
      if (err instanceof JobConflictError) {
        if (err.conflict.kind === "create_subtitles") {
          setCreateSubtitlesError(null);
          setIsCreatingSubtitles(true);
          createSubtitlesJobIdRef.current = err.conflict.job_id;
          const eventsUrl =
            err.conflict.events_url ?? `http://127.0.0.1:8765/jobs/${err.conflict.job_id}/events`;
          setPersistedRunningJob(projectId, {
            jobId: err.conflict.job_id,
            eventsUrl,
            kind: "create_subtitles"
          });
          openCreateSubtitlesStream(err.conflict.job_id, err.conflict.events_url);
          setProjectReloadTick((prev) => prev + 1);
          return;
        }
        setIsCreatingSubtitles(false);
        clearPreparingPreviewTimers();
        preparingPreviewStartedAtRef.current = null;
        closeCreateSubtitlesStream("create_subtitles_start_conflict");
        setCreateStreamHealthValue("idle");
        setCreateSubtitlesStartedAt(null);
        setCreateSubtitlesError("Another task is already running for this video.");
        return;
      }
      setIsCreatingSubtitles(false);
      clearPreparingPreviewTimers();
      preparingPreviewStartedAtRef.current = null;
      closeCreateSubtitlesStream("create_subtitles_start_failed");
      setCreateStreamHealthValue("idle");
      setCreateSubtitlesStartedAt(null);
      setCreateSubtitlesError(
        messageForBackendError(err, err instanceof Error ? err.message : "Failed to start subtitle generation.")
      );
    }
  }, [
    buildJobOptions,
    clearTimingFallbackProgress,
    clearPreparingPreviewTimers,
    closeCreateSubtitlesStream,
    handleCreateSubtitlesEvent,
    isCreatingSubtitles,
    isExporting,
    openCreateSubtitlesStream,
    project,
    projectId,
    registerRunningJob,
    resolveOutputDir,
    setCreateStreamHealthValue,
    settings,
    startCreateStreamCooldown
  ]);

  const cancelCreateSubtitles = React.useCallback(() => {
    const jobId =
      createSubtitlesJobStreamRef.current?.jobId ??
      createSubtitlesJobIdRef.current ??
      (typeof project?.active_task?.job_id === "string" ? project.active_task.job_id : null);
    if (!jobId || !projectId) {
      return;
    }
    clearPreparingPreviewTimers();
    preparingPreviewStartedAtRef.current = null;
    createSubtitlesUnregisterRef.current?.();
    createSubtitlesUnregisterRef.current = null;
    if (elevatorMusicTimerRef.current) {
      clearTimeout(elevatorMusicTimerRef.current);
      elevatorMusicTimerRef.current = null;
    }
    elevatorMusicRowScheduledRef.current = false;
    setShowElevatorMusicRow(false);
    setElevatorMusicPlaying(false);
    elevatorAudioRef.current?.pause();
    selectedElevatorTrackIndexRef.current = null;
    const projectTitle = resolveTitle(project);
    navigate("/", {
      state: {
        cancelledCreateProjectId: projectId,
        cancelledCreateProjectTitle: projectTitle
      }
    });
    void (async () => {
      try {
        if (createSubtitlesJobStreamRef.current?.jobId === jobId) {
          await createSubtitlesJobStreamRef.current.cancel();
          return;
        }
        await cancelJob(jobId);
      } catch {
        // Best-effort cancel; ProjectHub handles project cleanup and user-facing recovery.
      }
    })();
  }, [
    clearPreparingPreviewTimers,
    navigate,
    project,
    projectId
  ]);

  const handleElevatorMusicToggle = React.useCallback(() => {
    let audio = elevatorAudioRef.current;
    if (elevatorMusicPlaying) {
      audio?.pause();
      setElevatorMusicPlaying(false);
      return;
    }
    if (!audio) {
      audio = new Audio();
      elevatorAudioRef.current = audio;
      audio.loop = true;
      audio.addEventListener("ended", () => setElevatorMusicPlaying(false));
    }
    const hadTrack = selectedElevatorTrackIndexRef.current !== null;
    if (!hadTrack) {
      selectedElevatorTrackIndexRef.current = Math.floor(
        Math.random() * ELEVATOR_MUSIC_TRACK_NAMES.length
      );
    }
    const idx = selectedElevatorTrackIndexRef.current;
    const name = ELEVATOR_MUSIC_TRACK_NAMES[idx ?? 0];
    if (name) {
      if (!hadTrack) {
        audio.src = getElevatorMusicTrackUrl(name);
      }
      audio.play().then(() => setElevatorMusicPlaying(true)).catch(() => {});
    }
  }, [elevatorMusicPlaying]);

  const handleExportEvent = React.useCallback(
    (event: JobEvent) => {
      noteExportLiveEventTimestamp(event);
      if (event.type === "started") {
        setExportHeading(asNonEmptyString(event.heading) ?? "Exporting video");
        setExportStartedAt(asString(event.ts) ?? new Date().toISOString());
        return;
      }
      if (event.type === "checklist") {
        const stepId = asString(event.step_id);
        const state = asString(event.state);
        if (!stepId || !state) {
          return;
        }
        updateExportChecklist(stepId, state, resolveChecklistReason(event));
        return;
      }
      if (event.type === "progress") {
        if (typeof event.pct === "number") {
          setExportProgressPct(event.pct);
        }
        const message = asString(event.message);
        if (message) {
          setExportProgressMessage(message);
        }
        return;
      }
      if (event.type === "result") {
        const payload =
          event.payload && typeof event.payload === "object"
            ? (event.payload as Record<string, unknown>)
            : null;
        if (payload && typeof payload.output_path === "string") {
          const outputPath = payload.output_path as string;
          setExportOutputPath(outputPath);
          const exportedAt =
            typeof payload.exported_at === "string" ? payload.exported_at : "";
          const filename =
            outputPath.split(/[/\\]/).filter(Boolean).pop() ?? outputPath;
          const actions: { label: string; onClick: () => void }[] = [];
          if (isTauriEnv) {
            actions.push(
              {
                label: "Play",
                onClick: () => {
                  void openPath(outputPath);
                }
              },
              {
                label: "Open folder",
                onClick: () => {
                  void revealItemInDir(outputPath);
                }
              }
            );
          }
          if (
            projectId &&
            !haveExportCompleteBeenSeen(projectId, outputPath, exportedAt)
          ) {
            markExportCompleteSeen(projectId, outputPath, exportedAt);
            pushToast("Export complete", filename, { actions });
          }
        }
        return;
      }
      if (event.type === "completed") {
        exportUnregisterRef.current?.();
        exportUnregisterRef.current = null;
        setExportProgressPct(100);
        setIsExporting(false);
        setExportStartedAt(null);
        exportJobIdRef.current = null;
        if (exportStreamCooldownTimerRef.current !== null) {
          clearTimeout(exportStreamCooldownTimerRef.current);
          exportStreamCooldownTimerRef.current = null;
        }
        exportStreamCooldownUntilRef.current = 0;
        closeExportStream("export_completed");
        setExportStreamHealthValue("idle");
        setProjectReloadTick((prev) => prev + 1);
        return;
      }
      if (event.type === "cancelled") {
        exportUnregisterRef.current?.();
        exportUnregisterRef.current = null;
        setExportProgressPct(0);
        setExportProgressMessage("");
        setIsExporting(false);
        setExportStartedAt(null);
        exportJobIdRef.current = null;
        setExportError(null);
        if (exportStreamCooldownTimerRef.current !== null) {
          clearTimeout(exportStreamCooldownTimerRef.current);
          exportStreamCooldownTimerRef.current = null;
        }
        exportStreamCooldownUntilRef.current = 0;
        closeExportStream("export_cancelled");
        setExportStreamHealthValue("idle");
        return;
      }
      if (event.type === "error") {
        exportUnregisterRef.current?.();
        exportUnregisterRef.current = null;
        setExportProgressPct(0);
        setExportProgressMessage("");
        setIsExporting(false);
        setExportStartedAt(null);
        exportJobIdRef.current = null;
        setExportError(asNonEmptyString(event.message) ?? "Video export failed.");
        if (exportStreamCooldownTimerRef.current !== null) {
          clearTimeout(exportStreamCooldownTimerRef.current);
          exportStreamCooldownTimerRef.current = null;
        }
        exportStreamCooldownUntilRef.current = 0;
        closeExportStream("export_error");
        setExportStreamHealthValue("idle");
      }
    },
    [
      closeExportStream,
      haveExportCompleteBeenSeen,
      isTauriEnv,
      markExportCompleteSeen,
      noteExportLiveEventTimestamp,
      projectId,
      pushToast,
      resolveChecklistReason,
      setExportStreamHealthValue,
      updateExportChecklist
    ]
  );

  const openExportStream = React.useCallback(
    (jobId: string, eventsUrl?: string) => {
      if (!jobId) {
        return;
      }
      if (
        exportStreamHealthRef.current === "cooldown" &&
        Date.now() < exportStreamCooldownUntilRef.current
      ) {
        return;
      }
      if (
        exportJobStreamRef.current?.jobId === jobId &&
        (exportStreamHealthRef.current === "open" ||
          exportStreamHealthRef.current === "connecting")
      ) {
        return;
      }
      closeExportStream("open_export_stream");
      setExportStreamHealthValue("connecting");
      let streamOpened = false;
      const stream = attachToJobEvents(
        jobId,
        {
          onEvent: handleExportEvent,
          onOpen: () => {
            if (exportJobStreamRef.current !== stream) {
              return;
            }
            streamOpened = true;
            exportStreamCooldownUntilRef.current = 0;
            if (exportStreamCooldownTimerRef.current !== null) {
              clearTimeout(exportStreamCooldownTimerRef.current);
              exportStreamCooldownTimerRef.current = null;
            }
            setExportStreamHealthValue("open");
          },
          onError: () => {
            if (exportJobStreamRef.current !== stream) {
              return;
            }
            closeExportStream("export_stream_error");
            if (!streamOpened) {
              startExportStreamCooldown();
            }
            setProjectReloadTick((prev) => prev + 1);
          }
        },
        eventsUrl
      );
      exportJobIdRef.current = jobId;
      exportJobStreamRef.current = stream;
      setExportJobStream(stream);
      exportUnregisterRef.current?.();
      exportUnregisterRef.current = registerRunningJob({
        id: jobId,
        label: `Exporting ${resolveTitle(project)}`,
        cancel: () => stream.cancel()
      });
    },
    [
      closeExportStream,
      handleExportEvent,
      project,
      registerRunningJob,
      setExportStreamHealthValue,
      startExportStreamCooldown
    ]
  );

  const startExport = React.useCallback(async () => {
    if (!projectId || !project?.video?.path || isExporting) {
      return;
    }
    if (isCreatingSubtitles && project?.active_task?.kind === "create_subtitles") {
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
        style: buildProjectStylePayload(
          appearance,
          preset,
          highlightOpacity,
          lastPresetId
        )
      });
    } catch (err) {
      setExportError(messageForBackendError(err, err instanceof Error ? err.message : "Failed to save style before export."));
      return;
    }
    setExportError(null);
    setExportHeading("Exporting video");
    setExportProgressPct(0);
    setExportProgressMessage("Starting...");
    setExportChecklist(defaultChecklist(buildExportChecklist()));
    latestExportLiveEventAtMsRef.current = 0;
    if (exportStreamCooldownTimerRef.current !== null) {
      clearTimeout(exportStreamCooldownTimerRef.current);
      exportStreamCooldownTimerRef.current = null;
    }
    exportStreamCooldownUntilRef.current = 0;
    closeExportStream("start_export");
    setExportStreamHealthValue("connecting");
    setIsExporting(true);
    setExportStartedAt(new Date().toISOString());
    let streamOpened = false;
    try {
      const job = await createVideoWithSubtitlesJob(
        {
          projectId,
          outputDir: resolvedOutputDir,
          options: buildJobOptions(settings)
        },
        {
          onEvent: handleExportEvent,
          onOpen: () => {
            streamOpened = true;
            exportStreamCooldownUntilRef.current = 0;
            if (exportStreamCooldownTimerRef.current !== null) {
              clearTimeout(exportStreamCooldownTimerRef.current);
              exportStreamCooldownTimerRef.current = null;
            }
            setExportStreamHealthValue("open");
          },
          onError: () => {
            closeExportStream("export_start_stream_error");
            if (!streamOpened) {
              startExportStreamCooldown();
            }
            setExportProgressMessage("Syncing progress...");
            setProjectReloadTick((prev) => prev + 1);
          }
        }
      );
      exportJobIdRef.current = job.jobId;
      exportJobStreamRef.current = job;
      setExportJobStream(job);
      exportUnregisterRef.current?.();
      exportUnregisterRef.current = registerRunningJob({
        id: job.jobId,
        label: `Exporting ${resolveTitle(project)}`,
        cancel: () => job.cancel()
      });
    } catch (err) {
      if (err instanceof JobConflictError) {
        if (err.conflict.kind === "create_video_with_subtitles") {
          setExportError(null);
          setIsExporting(true);
          exportJobIdRef.current = err.conflict.job_id;
          openExportStream(err.conflict.job_id, err.conflict.events_url);
          setProjectReloadTick((prev) => prev + 1);
          return;
        }
        setIsExporting(false);
        closeExportStream("export_start_conflict");
        setExportStreamHealthValue("idle");
        setExportStartedAt(null);
        setExportError("Subtitles are still being created for this video.");
        return;
      }
      setIsExporting(false);
      closeExportStream("export_start_failed");
      setExportStreamHealthValue("idle");
      setExportStartedAt(null);
      setExportError(messageForBackendError(err, err instanceof Error ? err.message : "Failed to start video export."));
    }
  }, [
    buildProjectStylePayload,
    buildJobOptions,
    closeExportStream,
    handleExportEvent,
    isCreatingSubtitles,
    isExporting,
    openExportStream,
    preset,
    project,
    projectId,
    registerRunningJob,
    resolveOutputDir,
    setExportStreamHealthValue,
    settings,
    startExportStreamCooldown,
    appearance,
    highlightOpacity
  ]);

  const cancelExport = React.useCallback(async () => {
    const jobId =
      exportJobStreamRef.current?.jobId ??
      exportJobIdRef.current ??
      (typeof project?.active_task?.job_id === "string" ? project.active_task.job_id : null);
    if (!jobId) {
      return;
    }
    exportUnregisterRef.current?.();
    exportUnregisterRef.current = null;
    if (exportJobStreamRef.current?.jobId === jobId) {
      await exportJobStreamRef.current.cancel();
      return;
    }
    await cancelJob(jobId);
  }, [project?.active_task?.job_id]);

  React.useEffect(() => {
    if (!project) {
      return;
    }
    const activeTask = project.active_task;
    if (
      activeTask &&
      typeof activeTask.job_id === "string" &&
      (activeTask.kind === "create_subtitles" || activeTask.kind === "create_video_with_subtitles")
    ) {
      const pct =
        typeof activeTask.pct === "number" ? Math.max(0, Math.min(100, activeTask.pct)) : 0;
      const message = typeof activeTask.message === "string" ? activeTask.message : "";
      const startedAt =
        typeof activeTask.started_at === "string"
          ? activeTask.started_at
          : typeof activeTask.updated_at === "string"
            ? activeTask.updated_at
            : null;
      const snapshotUpdatedAtMs = parseIsoTimestampMs(activeTask.updated_at);
      const checklist = buildChecklistFromActiveTask(activeTask);
      if (activeTask.kind === "create_subtitles") {
        const createStreamOpenForJob =
          createSubtitlesStreamHealthRef.current === "open" &&
          createSubtitlesJobStreamRef.current?.jobId === activeTask.job_id;
        const shouldApplyCreateSnapshot =
          !createStreamOpenForJob ||
          snapshotUpdatedAtMs >= latestCreateLiveEventAtMsRef.current;
        setIsCreatingSubtitles(true);
        setCreateSubtitlesError(null);
        setIsExporting(false);
        setExportStartedAt(null);
        setExportError(null);
        exportJobIdRef.current = null;
        closeExportStream("switch_to_create_subtitles");
        setExportStreamHealthValue("idle");
        if (shouldApplyCreateSnapshot) {
          setCreateSubtitlesHeading(
            activeTask.status === "queued" ? "Queued" : (activeTask.heading ?? "Creating subtitles")
          );
          setCreateSubtitlesProgressPct(pct);
          setCreateSubtitlesProgressMessage(message);
          const fullList = defaultChecklist(buildGenerateChecklist(settings ?? {}));
          const merged =
            checklist.length > 0
              ? fullList.map((fullItem) => {
                  const fromApi = checklist.find((c) => c.id === fullItem.id);
                  if (fromApi)
                    return {
                      ...fullItem,
                      state: normalizeChecklistState(fromApi.state),
                      detail:
                        typeof fromApi.detail === "string" && fromApi.detail.trim()
                          ? fromApi.detail.trim()
                          : fullItem.detail
                    };
                  return fullItem;
                })
              : fullList;
          const timingItem = merged.find((item) => item.id === checklistStepIds.timingWordHighlights);
          rememberTimingAuthoritativeDetail(timingItem?.detail, activeTask.updated_at);
          setCreateSubtitlesChecklist(merged);
          const isPreparingPreviewActive = merged.some(
            (item) => item.id === checklistStepIds.preparingPreview && item.state === "active"
          );
          if (isPreparingPreviewActive) {
            if (preparingPreviewStartedAtRef.current == null) {
              preparingPreviewStartedAtRef.current = Date.now();
            }
          } else if (!preparingPreviewCompletionScheduledRef.current) {
            preparingPreviewStartedAtRef.current = null;
          }
          setCreateSubtitlesStartedAt((prev) => {
            if (!startedAt) return prev;
            if (!prev) return startedAt;
            const prevMs = Date.parse(prev);
            const serverMs = Date.parse(startedAt);
            if (!Number.isFinite(prevMs) || !Number.isFinite(serverMs)) return prev ?? startedAt;
            return prevMs <= serverMs ? prev : startedAt;
          });
        }
        createSubtitlesJobIdRef.current = activeTask.job_id;
        if (!createStreamOpenForJob) {
          openCreateSubtitlesStream(activeTask.job_id);
        }
      } else if (activeTask.kind === "create_video_with_subtitles") {
        const exportStreamOpenForJob =
          exportStreamHealthRef.current === "open" &&
          exportJobStreamRef.current?.jobId === activeTask.job_id;
        const shouldApplyExportSnapshot =
          !exportStreamOpenForJob ||
          snapshotUpdatedAtMs >= latestExportLiveEventAtMsRef.current;
        clearPreparingPreviewTimers();
        preparingPreviewStartedAtRef.current = null;
        setIsCreatingSubtitles(false);
        setCreateSubtitlesStartedAt(null);
        setCreateSubtitlesError(null);
        createSubtitlesJobIdRef.current = null;
        createSubtitlesUnregisterRef.current?.();
        createSubtitlesUnregisterRef.current = null;
        closeCreateSubtitlesStream("switch_to_export");
        setCreateStreamHealthValue("idle");
        clearTimingFallbackProgress();
        setIsExporting(true);
        setExportError(null);
        if (shouldApplyExportSnapshot) {
          setExportHeading(
            activeTask.status === "queued" ? "Queued" : (activeTask.heading ?? "Exporting video")
          );
          setExportProgressPct(pct);
          setExportProgressMessage(message);
          if (checklist.length > 0) {
            setExportChecklist(checklist);
          }
          setExportStartedAt(startedAt);
        }
        exportJobIdRef.current = activeTask.job_id;
        if (!exportStreamOpenForJob) {
          openExportStream(activeTask.job_id);
        }
      }
      return;
    }

    if (!activeTask && projectId) {
      const persisted = getPersistedRunningJob(projectId);
      if (persisted?.kind === "create_subtitles") {
        const isSameSessionJustStarted =
          createSubtitlesJustStartedRef.current ||
          (createSubtitlesJobIdRef.current === persisted.jobId && createSubtitlesStartedAt != null);
        setIsCreatingSubtitles(true);
        setCreateSubtitlesError(null);
        setIsExporting(false);
        setExportStartedAt(null);
        setExportError(null);
        exportJobIdRef.current = null;
        closeExportStream("resume_persisted_create");
        setExportStreamHealthValue("idle");
        setCreateSubtitlesHeading("Creating subtitles");
        setCreateSubtitlesProgressPct(0);
        if (!isSameSessionJustStarted) {
          setCreateSubtitlesProgressMessage("");
          setCreateSubtitlesChecklist(
            settings ? defaultChecklist(buildGenerateChecklist(settings)) : []
          );
          setCreateSubtitlesStartedAt(null);
        }
        createSubtitlesJobIdRef.current = persisted.jobId;
        if (
          createSubtitlesJobStreamRef.current?.jobId !== persisted.jobId ||
          createSubtitlesStreamHealthRef.current !== "open"
        ) {
          openCreateSubtitlesStream(persisted.jobId, persisted.eventsUrl);
        }
        return;
      }
    }

    const taskNotice = project.task_notice;
    if (!activeTask && createSubtitlesJobIdRef.current) {
      createSubtitlesUnregisterRef.current?.();
      createSubtitlesUnregisterRef.current = null;
      createSubtitlesJobIdRef.current = null;
    }
    if (
      !activeTask &&
      isCreatingSubtitles &&
      (createSubtitlesStreamHealthRef.current !== "open" || !createSubtitlesJobIdRef.current)
    ) {
      clearPreparingPreviewTimers();
      preparingPreviewStartedAtRef.current = null;
      createSubtitlesUnregisterRef.current?.();
      createSubtitlesUnregisterRef.current = null;
      const hadJobRef = Boolean(createSubtitlesJobIdRef.current);
      const finishedJobId = createSubtitlesJobIdRef.current;
      createSubtitlesJobIdRef.current = null;
      if (projectId) clearPersistedRunningJob(projectId);
      setIsCreatingSubtitles(false);
      setCreateSubtitlesStartedAt(null);
      setCreateSubtitlesProgressMessage("");
      clearTimingFallbackProgress();
      if (hadJobRef && taskNotice?.job_id === finishedJobId && taskNotice.status !== "completed") {
        setCreateSubtitlesError(normalizeCreateSubtitlesErrorMessage(taskNotice.message));
        setCreateSubtitlesProgressPct(0);
      } else {
        setCreateSubtitlesProgressPct(100);
        if (hadJobRef) setSubtitlesReloadTick((prev) => prev + 1);
      }
    }
    if (
      !activeTask &&
      exportJobIdRef.current &&
      isExporting &&
      exportStreamHealthRef.current !== "open"
    ) {
      exportUnregisterRef.current?.();
      exportUnregisterRef.current = null;
      const finishedJobId = exportJobIdRef.current;
      exportJobIdRef.current = null;
      setIsExporting(false);
      setExportStartedAt(null);
      setExportProgressMessage("");
      if (
        taskNotice?.job_id === finishedJobId &&
        taskNotice.status !== "completed" &&
        taskNotice.status !== "cancelled"
      ) {
        setExportError(taskNotice.message);
        setExportProgressPct(0);
      } else {
        setExportError(null);
        setExportProgressPct(taskNotice?.status === "cancelled" ? 0 : 100);
      }
    }
  }, [
    clearTimingFallbackProgress,
    clearPreparingPreviewTimers,
    createSubtitlesStartedAt,
    closeCreateSubtitlesStream,
    closeExportStream,
    createSubtitlesStreamHealth,
    exportStreamHealth,
    isCreatingSubtitles,
    isExporting,
    openCreateSubtitlesStream,
    openExportStream,
    project,
    projectId,
    rememberTimingAuthoritativeDetail,
    setCreateStreamHealthValue,
    setExportStreamHealthValue,
    settings
  ]);

  React.useEffect(() => {
    if (!projectId) {
      return;
    }
    const shouldPollCreateSync = isCreatingSubtitles && createSubtitlesStreamHealth !== "open";
    const shouldPollExportSync = isExporting && exportStreamHealth !== "open";
    if (!shouldPollCreateSync && !shouldPollExportSync) {
      return;
    }
    const timer = window.setInterval(() => {
      setProjectReloadTick((prev) => prev + 1);
    }, ACTIVE_TASK_SYNC_POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [
    createSubtitlesStreamHealth,
    exportStreamHealth,
    isCreatingSubtitles,
    isExporting,
    projectId
  ]);

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
  const hasActiveCreateFromApi = project?.active_task?.kind === "create_subtitles";
  const canExport =
    hasSubtitles &&
    !isExporting &&
    (!isCreatingSubtitles || !hasActiveCreateFromApi);
  const showNoSubtitlesState = !isLoading && !error && !subtitleLoadError && !hasSubtitles;
  const persistedCreateJob = projectId ? getPersistedRunningJob(projectId) : null;
  const hasActiveCreateSubtitles =
    isCreatingSubtitles ||
    project?.active_task?.kind === "create_subtitles" ||
    persistedCreateJob?.kind === "create_subtitles";
  const hasVideoPreview = Boolean(previewSrc);
  const showLeftToggle = showSubtitlesOverlay && !leftPanelOpen;
  const isOverlayOpen =
    (showSubtitlesOverlay && leftPanelOpen) || rightOverlayOpen;
  const showScrim =
    isNarrow &&
    (hasSubtitles && ((showSubtitlesOverlay && leftPanelOpen) || rightOverlayOpen));
  const activeCue = React.useMemo(() => {
    return (
      cues.find(
        (cue) => cue.startSeconds <= currentTimeSeconds && currentTimeSeconds <= cue.endSeconds
      ) ?? null
    );
  }, [cues, currentTimeSeconds]);
  const activeCueOrdinal = React.useMemo(() => {
    if (!activeCue) {
      return null;
    }
    const cuePosition = cues.findIndex((cue) => cue.id === activeCue.id);
    return cuePosition >= 0 ? cuePosition + 1 : null;
  }, [activeCue, cues]);
  const cueWordTimingsByIndex = React.useMemo(() => {
    const mapping = new Map<number, ProjectWordTimingCue>();
    if (!wordTimingsDoc || !Array.isArray(wordTimingsDoc.cues)) {
      return mapping;
    }
    for (const cueTiming of wordTimingsDoc.cues) {
      if (typeof cueTiming.cue_index !== "number" || !Number.isFinite(cueTiming.cue_index)) {
        continue;
      }
      mapping.set(cueTiming.cue_index, cueTiming);
    }
    return mapping;
  }, [wordTimingsDoc]);
  const isEditingCue = editingCueId !== null;
  const isActiveCueSelected = activeCue ? selectedCueId === activeCue.id : false;
  const isEditingActiveCue = activeCue ? editingCueId === activeCue.id : false;
  const cueSegments = React.useMemo(
    () => (activeCue ? activeCue.text.split(/(\s+)/) : []),
    [activeCue]
  );
  const cueWordCount = React.useMemo(
    () => cueSegments.reduce((count, segment) => count + (/\S/.test(segment) ? 1 : 0), 0),
    [cueSegments]
  );
  const editingSegments = React.useMemo(
    () => (isEditingActiveCue ? editingText.split(/(\s+)/) : []),
    [editingText, isEditingActiveCue]
  );
  const editingWordCount = React.useMemo(
    () =>
      editingSegments.reduce((count, segment) => count + (/\S/.test(segment) ? 1 : 0), 0),
    [editingSegments]
  );
  const highlightedWordIndex = React.useMemo(() => {
    if (!activeCue || appearance.subtitle_mode !== "word_highlight" || cueWordCount <= 0) {
      return null;
    }
    if (activeCueOrdinal === null) {
      return null;
    }
    const cueTiming = cueWordTimingsByIndex.get(activeCueOrdinal);
    return resolveHighlightWordIndexFromTimings(activeCue, currentTimeSeconds, cueTiming);
  }, [
    activeCue,
    activeCueOrdinal,
    appearance.subtitle_mode,
    cueWordCount,
    cueWordTimingsByIndex,
    currentTimeSeconds
  ]);
  const highlightWordColor = colorWithOpacity(appearance.highlight_color, highlightOpacity);
  const defaultSubtitleTextColor = colorWithOpacity(appearance.text_color, appearance.text_opacity);
  const hasWordBackground = appearance.background_mode === "word";
  const activeCueHasRtlChars = activeCue ? RTL_CHAR_PATTERN.test(activeCue.text) : false;
  const subtitleDirection: "rtl" | "auto" = activeCueHasRtlChars ? "rtl" : "auto";
  const wordPadT = appearance.word_bg_padding_top ?? appearance.word_bg_padding ?? 8;
  const wordPadR = appearance.word_bg_padding_right ?? appearance.word_bg_padding ?? 8;
  const wordPadB = appearance.word_bg_padding_bottom ?? appearance.word_bg_padding ?? 8;
  const wordPadL = appearance.word_bg_padding_left ?? appearance.word_bg_padding ?? 8;
  const activeWordStyle: React.CSSProperties = hasWordBackground
    ? {}
    : {};
  const wordBgBackingStyle: React.CSSProperties =
    hasWordBackground
      ? {
          position: "absolute",
          left: -Math.max(0, wordPadL),
          top: -Math.max(0, wordPadT),
          right: -Math.max(0, wordPadR),
          bottom: -Math.max(0, wordPadB),
          backgroundColor: colorWithOpacity(appearance.word_bg_color, appearance.word_bg_opacity),
          borderRadius: `${Math.max(0, appearance.word_bg_radius)}px`,
          zIndex: -1,
          pointerEvents: "none"
        }
      : {};
  const subtitleOverlaySrc = React.useMemo(() => {
    if (!subtitleOverlayPath) {
      return null;
    }
    const base = isTauriEnv ? convertFileSrc(subtitleOverlayPath) : subtitleOverlayPath;
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}v=${encodeURIComponent(appearance.font_family)}`;
  }, [isTauriEnv, subtitleOverlayPath, appearance.font_family]);
  const SHOW_SUBTITLE_OVERLAY_IN_APP = false;
  const shouldRenderOverlayImage = Boolean(subtitleOverlaySrc && activeCue && !isEditingActiveCue);

  React.useEffect(() => {
    setSubtitleOverlayPath(null);
    setVideoNaturalSize({ width: 0, height: 0 });
    setDurationSeconds(0);
    setIsPlaying(false);
    overlayRequestKeyRef.current = null;
  }, [videoPath]);

  React.useEffect(() => {
    if (
      !isTauriEnv ||
      !activeCue ||
      isEditingActiveCue ||
      videoNaturalSize.width <= 0 ||
      videoNaturalSize.height <= 0
    ) {
      setSubtitleOverlayPath(null);
      overlayRequestKeyRef.current = null;
      return;
    }

    const resolvedAppearance = {
      ...appearance,
      outline_color: resolveOutlineColor(
        appearance.outline_color,
        appearance.text_color
      )
    };
    const requestPayload = {
      width: videoNaturalSize.width,
      height: videoNaturalSize.height,
      subtitle_text: activeCue.text,
      highlight_word_index: highlightedWordIndex,
      subtitle_style: resolvedAppearance,
      subtitle_mode: appearance.subtitle_mode,
      highlight_color: appearance.highlight_color,
      highlight_opacity: highlightOpacity
    };
    const requestKey = JSON.stringify(requestPayload);
    if (overlayRequestKeyRef.current === requestKey) {
      return;
    }
    overlayRequestKeyRef.current = requestKey;

    let cancelled = false;
    void previewOverlay(requestPayload)
      .then((result) => {
        if (cancelled || overlayRequestKeyRef.current !== requestKey) {
          return;
        }
        if (typeof result.overlay_path === "string" && result.overlay_path) {
          setSubtitleOverlayPath(result.overlay_path);
          return;
        }
        setSubtitleOverlayPath(null);
      })
      .catch((err) => {
        if (cancelled || overlayRequestKeyRef.current !== requestKey) {
          return;
        }
        setSubtitleOverlayPath(null);
        console.error("Failed to render subtitle preview overlay.", err);
      });
    return () => {
      cancelled = true;
    };
  }, [
    activeCue,
    appearance,
    highlightOpacity,
    highlightedWordIndex,
    isEditingActiveCue,
    isTauriEnv,
    videoNaturalSize.height,
    videoNaturalSize.width
  ]);

  const openSystemPath = React.useCallback(
    async (rawPath: string) => {
      if (!isTauriEnv) {
        throw new Error("Open actions are only available in the desktop app runtime.");
      }
      const candidates = buildPathCandidates(rawPath);
      if (candidates.length === 0) {
        throw new Error("No path was available to open.");
      }
      let lastError: unknown = null;
      for (const candidate of candidates) {
        try {
          await openPath(candidate);
          return;
        } catch (err) {
          lastError = err;
        }
      }
      throw lastError ?? new Error("Unable to open the requested path.");
    },
    [isTauriEnv]
  );
  const openLatestOutputVideo = React.useCallback(async () => {
    if (!latestOutputPath) {
      return;
    }
    setOpenActionError(null);
    try {
      await openSystemPath(latestOutputPath);
    } catch (err) {
      const detail = describeOpenError(err);
      setOpenActionError(`Could not open video: ${detail}`);
      console.error("Failed to open exported video.", { path: latestOutputPath, error: err });
    }
  }, [latestOutputPath, openSystemPath]);

  const openLatestOutputFolder = React.useCallback(async () => {
    if (!latestOutputPath) {
      return;
    }
    const normalizedOutputPath = normalizePathInput(latestOutputPath);
    const folderPath = getDirName(normalizedOutputPath);
    if (!folderPath) {
      setOpenActionError("Could not open folder: Unable to determine the export folder path.");
      return;
    }
    setOpenActionError(null);
    try {
      await openSystemPath(folderPath);
      return;
    } catch (openErr) {
      if (isTauriEnv) {
        try {
          await revealItemInDir(normalizedOutputPath);
          return;
        } catch (revealErr) {
          const detail = describeOpenError(revealErr);
          setOpenActionError(`Could not open folder: ${detail}`);
          console.error("Failed to reveal exported video in folder.", {
            outputPath: normalizedOutputPath,
            folderPath,
            error: revealErr
          });
          return;
        }
      }
      const detail = describeOpenError(openErr);
      setOpenActionError(`Could not open folder: ${detail}`);
      console.error("Failed to open export folder.", {
        outputPath: normalizedOutputPath,
        folderPath,
        error: openErr
      });
    }
  }, [isTauriEnv, latestOutputPath, openSystemPath]);

  const subtitleVerticalClass =
    appearance.vertical_anchor === "top"
      ? "items-start"
      : appearance.vertical_anchor === "middle"
        ? "items-center"
        : "items-end";
  /** For flex-col containers: vertical position is controlled by justify-content, not align-items. */
  const subtitleVerticalJustifyClass =
    appearance.vertical_anchor === "top"
      ? "justify-start"
      : appearance.vertical_anchor === "middle"
        ? "justify-center"
        : "justify-end";

  const subtitleOverlayPositionStyle = React.useMemo<React.CSSProperties>(() => {
    const scaledOffset = Math.max(0, appearance.vertical_offset * displayedVideoRect.scale);
    const offsetPx = `${scaledOffset}px`;
    let style: React.CSSProperties;
    if (appearance.vertical_anchor === "top") {
      style = { paddingTop: offsetPx };
    } else if (appearance.vertical_anchor === "middle") {
      style = { transform: `translateY(-${scaledOffset}px)` };
    } else {
      style = { paddingBottom: offsetPx };
    }
    return style;
  }, [appearance.vertical_anchor, appearance.vertical_offset, displayedVideoRect.scale]);

  const displayedVideoGeometryStyle = React.useMemo<React.CSSProperties>(
    () => ({
      left: `${displayedVideoRect.offsetX}px`,
      top: `${displayedVideoRect.offsetY}px`,
      width: `${displayedVideoRect.width}px`,
      height: `${displayedVideoRect.height}px`
    }),
    [displayedVideoRect.height, displayedVideoRect.offsetX, displayedVideoRect.offsetY, displayedVideoRect.width]
  );

  const VIDEO_CONTROL_BAR_HEIGHT_PX = 44;
  const VIDEO_PROGRESS_STRIP_HEIGHT_PX = 6;
  const VIDEO_PROGRESS_STRIP_HEIGHT_PX_HOVER = 9;
  const VIDEO_PROGRESS_STRIP_PADDING_PX = 8;
  const VIDEO_PROGRESS_THUMB_SIZE_PX = 12;
  const effectiveProgressStripHeightPx =
    progressHoverSeconds !== null ? VIDEO_PROGRESS_STRIP_HEIGHT_PX_HOVER : VIDEO_PROGRESS_STRIP_HEIGHT_PX;
  const VIDEO_PROGRESS_HIT_AREA_PY = 16;
  const VIDEO_CONTROLS_TOTAL_HEIGHT_PX =
    VIDEO_CONTROL_BAR_HEIGHT_PX +
    8 +
    VIDEO_PROGRESS_HIT_AREA_PY * 2 +
    VIDEO_PROGRESS_STRIP_HEIGHT_PX_HOVER +
    8;
  const videoControlsBarContainerStyle = React.useMemo<React.CSSProperties>(() => {
    const totalHeight = VIDEO_CONTROLS_TOTAL_HEIGHT_PX;
    return {
      position: "absolute",
      left: `${displayedVideoRect.offsetX}px`,
      top: `${displayedVideoRect.offsetY + displayedVideoRect.height - totalHeight}px`,
      width: `${displayedVideoRect.width}px`,
      height: `${totalHeight}px`,
      zIndex: 10
    };
  }, [
    VIDEO_CONTROLS_TOTAL_HEIGHT_PX,
    displayedVideoRect.height,
    displayedVideoRect.offsetX,
    displayedVideoRect.offsetY,
    displayedVideoRect.width
  ]);
  const subtitleControlsPushStyle = React.useMemo<React.CSSProperties>(() => {
    if (subtitleControlsPushPx <= SUBTITLE_CONTROLS_PUSH_TOLERANCE_PX) {
      return {};
    }
    return { transform: `translateY(-${subtitleControlsPushPx}px)` };
  }, [subtitleControlsPushPx]);

  const subtitlePreviewTextStyle = React.useMemo<React.CSSProperties>(() => {
    const visualScale = displayedVideoRect.scale;
    const fontScale = isTauriEnv ? visualScale * QT_POINT_TO_CSS_PX : visualScale;
    const computedFontSizePx = Math.max(10 * fontScale, appearance.font_size * fontScale);
    const lineHeightRatio = isTauriEnv
      ? QT_SUBTITLE_LINE_HEIGHT_RATIO
      : WEB_SUBTITLE_LINE_HEIGHT_RATIO;
    const style: React.CSSProperties = {
      fontFamily: appearance.font_family || DEFAULT_APPEARANCE.font_family,
      fontSize: `${computedFontSizePx}px`,
      lineHeight: `${computedFontSizePx * lineHeightRatio}px`,
      fontWeight: appearance.font_style === "bold" ? 700 : 400,
      fontStyle: appearance.font_style === "italic" ? "italic" : "normal",
      letterSpacing: `${appearance.letter_spacing * visualScale}px`,
      color: colorWithOpacity(appearance.text_color, appearance.text_opacity)
    };

    const shadows: string[] = [];
    if (appearance.outline_enabled && appearance.outline_width > 0) {
      const scaledOutlineWidth = Math.min(
        MAX_OUTLINE_SHADOW_RADIUS,
        appearance.outline_width * visualScale
      );
      shadows.push(
        ...buildOutlineShadows(
          resolveOutlineColor(appearance.outline_color, appearance.text_color),
          scaledOutlineWidth
        )
      );
    }
    if (appearance.shadow_enabled && appearance.shadow_strength > 0) {
      const blurRadius = Math.max(0, Math.round((appearance.shadow_blur ?? 6) * visualScale));
      shadows.push(
        `${appearance.shadow_offset_x * visualScale}px ${appearance.shadow_offset_y * visualScale}px ${blurRadius}px ${colorWithOpacity(
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
      const pt = (appearance.line_bg_padding_top ?? appearance.line_bg_padding ?? 8) * visualScale;
      const pr = (appearance.line_bg_padding_right ?? appearance.line_bg_padding ?? 8) * visualScale;
      const pb = (appearance.line_bg_padding_bottom ?? appearance.line_bg_padding ?? 8) * visualScale;
      const pl = (appearance.line_bg_padding_left ?? appearance.line_bg_padding ?? 8) * visualScale;
      const radius = appearance.line_bg_radius * visualScale;
      style.backgroundColor = backgroundColor;
      style.paddingTop = `${Math.max(0, pt)}px`;
      style.paddingRight = `${Math.max(0, pr)}px`;
      style.paddingBottom = `${Math.max(0, pb)}px`;
      style.paddingLeft = `${Math.max(0, pl)}px`;
      style.borderRadius = `${Math.max(0, radius)}px`;
    }

    return style;
  }, [appearance, displayedVideoRect.scale, isTauriEnv]);

  const subtitleEditorTextStyle = React.useMemo<React.CSSProperties>(
    () => ({
      ...subtitlePreviewTextStyle,
      boxSizing: "border-box",
      margin: 0,
      border: "none"
    }),
    [subtitlePreviewTextStyle]
  );

  React.useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement) {
      return;
    }

    const updateGeometry = () => {
      const sourceWidth = Math.max(0, Math.round(videoElement.videoWidth || videoNaturalSize.width || 0));
      const sourceHeight = Math.max(0, Math.round(videoElement.videoHeight || videoNaturalSize.height || 0));
      const clientWidth = Math.max(0, videoElement.clientWidth || 0);
      const clientHeight = Math.max(0, videoElement.clientHeight || 0);

      if (sourceWidth <= 0 || sourceHeight <= 0 || clientWidth <= 0 || clientHeight <= 0) {
        setDisplayedVideoRect((previous) =>
          previous.width === 0 &&
          previous.height === 0 &&
          previous.offsetX === 0 &&
          previous.offsetY === 0 &&
          previous.scale === 1
            ? previous
            : {
                width: 0,
                height: 0,
                offsetX: 0,
                offsetY: 0,
                scale: 1
              }
        );
        return;
      }

      const scale = Math.min(clientWidth / sourceWidth, clientHeight / sourceHeight);
      const width = sourceWidth * scale;
      const height = sourceHeight * scale;
      const offsetX = (clientWidth - width) / 2;
      const offsetY = (clientHeight - height) / 2;

      setDisplayedVideoRect((previous) => {
        const next = { width, height, offsetX, offsetY, scale };
        const hasMeaningfulChange =
          Math.abs(previous.width - next.width) > 0.5 ||
          Math.abs(previous.height - next.height) > 0.5 ||
          Math.abs(previous.offsetX - next.offsetX) > 0.5 ||
          Math.abs(previous.offsetY - next.offsetY) > 0.5 ||
          Math.abs(previous.scale - next.scale) > 0.001;
        return hasMeaningfulChange ? next : previous;
      });
    };

    updateGeometry();

    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateGeometry) : null;
    observer?.observe(videoElement);
    window.addEventListener("resize", updateGeometry);
    videoElement.addEventListener("loadeddata", updateGeometry);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", updateGeometry);
      videoElement.removeEventListener("loadeddata", updateGeometry);
    };
  }, [videoNaturalSize.height, videoNaturalSize.width]);

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

  React.useLayoutEffect(() => {
    if (!isEditingActiveCue) {
      return;
    }
    const textarea = activeSubtitleRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [displayedVideoRect.height, displayedVideoRect.scale, displayedVideoRect.width, editingText, isEditingActiveCue, subtitleEditorTextStyle]);

  React.useLayoutEffect(() => {
    if (!isEditingActiveCue) {
      return;
    }
    const textarea = activeSubtitleRef.current;
    if (!textarea) {
      return;
    }
    const font =
      appearance.font_family || DEFAULT_APPEARANCE.font_family;
    textarea.style.setProperty("font-family", font, "important");
    return () => {
      textarea.style.removeProperty("font-family");
    };
  }, [isEditingActiveCue, appearance.font_family]);

  React.useLayoutEffect(() => {
    if (!showVideoControls || !activeCue) {
      setSubtitleControlsPushPx((prev) =>
        Math.abs(prev) <= SUBTITLE_CONTROLS_PUSH_TOLERANCE_PX ? prev : 0
      );
      return;
    }
    const controlsBar = videoControlsBarRef.current;
    const subtitleWrapper = activeSubtitleWrapperRef.current;
    const positionLayer = subtitleOverlayPositionLayerRef.current;
    if (!controlsBar || !subtitleWrapper || !positionLayer) {
      return;
    }

    const controlsRect = controlsBar.getBoundingClientRect();
    const subtitleRect = subtitleWrapper.getBoundingClientRect();
    const positionLayerRect = positionLayer.getBoundingClientRect();
    if (controlsRect.height <= 0 || subtitleRect.height <= 0 || positionLayerRect.height <= 0) {
      return;
    }

    const overlapPx =
      subtitleRect.bottom + SUBTITLE_CONTROLS_COLLISION_GAP_PX - controlsRect.top;
    const availableAbovePx = Math.max(0, subtitleRect.top - positionLayerRect.top);
    if (!Number.isFinite(overlapPx) || !Number.isFinite(availableAbovePx)) {
      return;
    }
    setSubtitleControlsPushPx((previous) => {
      const requestedPushPx = Math.max(0, overlapPx + previous);
      const availablePushPx = Math.max(0, availableAbovePx + previous);
      const nextPushPx = Math.min(requestedPushPx, availablePushPx);
      if (!Number.isFinite(nextPushPx)) {
        return previous;
      }
      return Math.abs(previous - nextPushPx) <= SUBTITLE_CONTROLS_PUSH_TOLERANCE_PX
        ? previous
        : nextPushPx;
    });
  }, [
    activeCue,
    displayedVideoRect.height,
    displayedVideoRect.offsetX,
    displayedVideoRect.offsetY,
    displayedVideoRect.scale,
    displayedVideoRect.width,
    editingText,
    showVideoControls,
    subtitleEditorTextStyle,
    subtitlePreviewTextStyle
  ]);

  React.useLayoutEffect(() => {
    if (!isEditingActiveCue) {
      setSubtitleEditorControlsPlacement("below");
      return;
    }
    const positionLayer = subtitleOverlayPositionLayerRef.current;
    const textarea = activeSubtitleRef.current;
    const editorControls = subtitleEditorControlsRef.current;
    const controlsBar = videoControlsBarRef.current;
    if (!positionLayer || !textarea || !editorControls) {
      return;
    }
    const positionLayerRect = positionLayer.getBoundingClientRect();
    const textareaRect = textarea.getBoundingClientRect();
    const editorControlsHeight = editorControls.offsetHeight;
    const requiredBelowSpace = editorControlsHeight + SUBTITLE_EDITOR_CONTROLS_GAP_PX;
    const layerBottom = positionLayerRect.bottom;
    const bottomLimit =
      controlsBar
        ? Math.min(layerBottom, controlsBar.getBoundingClientRect().top)
        : layerBottom;
    const spaceBelow = bottomLimit - textareaRect.bottom;
    const nextPlacement = spaceBelow < requiredBelowSpace ? "above" : "below";
    setSubtitleEditorControlsPlacement((previous) =>
      previous === nextPlacement ? previous : nextPlacement
    );
  }, [appearance, displayedVideoRect.height, displayedVideoRect.scale, displayedVideoRect.width, editingText, isEditingActiveCue, subtitleControlsPushPx, subtitleEditorTextStyle]);

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
      nextHighlightOpacity: number,
      lastPresetIdValue: string | null
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
              nextHighlightOpacity,
              lastPresetIdValue
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
      nextHighlightOpacity: number,
      lastPresetIdValue: string | null
    ) => {
      void persistStyleSettings(
        nextAppearance,
        nextPreset,
        nextHighlightOpacity,
        lastPresetIdValue
      );
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
      debouncedPersistStyle(next, nextPreset, highlightOpacity, lastPresetId);
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
    if (nextPreset === "Custom" || !isNamedPresetId(nextPreset)) {
      return;
    }
    if (preset === "Custom") {
      customAppearanceRef.current = appearance;
    }
    const nextAppearance = applyPresetAppearance(nextPreset);
    if (!nextAppearance) {
      return;
    }
    setPreset(nextPreset);
    setLastPresetId(nextPreset);
    setAppearance(nextAppearance);
    debouncedPersistStyle(nextAppearance, nextPreset, highlightOpacity, nextPreset);
  };

  const handleHighlightOpacityChange = (nextHighlightOpacity: number) => {
    if (isExporting) {
      return;
    }
    setHighlightOpacity(nextHighlightOpacity);
    debouncedPersistStyle(
      appearance,
      preset,
      nextHighlightOpacity,
      lastPresetId
    );
  };

  const handleResetPreset = () => {
    if (isExporting) {
      return;
    }
    const targetPreset =
      preset === "Custom" ? (lastPresetId ?? "classic_static") : preset;
    const nextAppearance = isNamedPresetId(targetPreset)
      ? applyPresetAppearance(targetPreset)
      : null;
    if (!nextAppearance) {
      return;
    }
    setPreset(targetPreset);
    setLastPresetId(targetPreset);
    setAppearance(nextAppearance);
    customAppearanceRef.current = nextAppearance;
    void persistStyleSettings(
      nextAppearance,
      targetPreset,
      highlightOpacity,
      targetPreset
    );
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
      setIsHoveringActiveSubtitle(false);
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
      setEditError(messageForBackendError(err, err instanceof Error ? err.message : "Failed to save subtitle changes."));
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

  const handleVideoPlay = React.useCallback(() => {
    if (!isEditingCue) return;
    const videoElement = videoRef.current;
    if (videoElement) videoElement.pause();
    shouldResumePlaybackRef.current = true;
    if (!isSavingCue) void handleSaveEdit();
  }, [isEditingCue, isSavingCue, handleSaveEdit]);

  const handlePlayPauseToggle = React.useCallback(() => {
    const el = videoRef.current;
    if (!el) return;
    if (el.paused) {
      el.play().catch(() => {});
    } else {
      el.pause();
    }
  }, []);

  const progressBarTrackRef = React.useRef<HTMLDivElement | null>(null);
  const handleProgressBarPointer = React.useCallback(
    (clientX: number) => {
      const el = videoRef.current;
      const track = progressBarTrackRef.current;
      if (!el || !track || durationSeconds <= 0) return;
      const rect = track.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const newTime = frac * durationSeconds;
      el.currentTime = newTime;
      setCurrentTimeSeconds(newTime);
    },
    [durationSeconds]
  );
  const handleProgressBarClick = React.useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      event.preventDefault();
      handleProgressBarPointer(event.clientX);
    },
    [handleProgressBarPointer]
  );
  const handleProgressBarMouseDown = React.useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      event.preventDefault();
      handleProgressBarPointer(event.clientX);
      const onMove = (e: MouseEvent) => handleProgressBarPointer(e.clientX);
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [handleProgressBarPointer]
  );
  const handleProgressBarMouseMove = React.useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const track = progressBarTrackRef.current;
      if (!track || durationSeconds <= 0) return;
      const rect = track.getBoundingClientRect();
      const xPx = event.clientX - rect.left;
      const frac = Math.max(0, Math.min(1, xPx / rect.width));
      lastProgressHoverXPxRef.current = xPx;
      setProgressHoverXPx(xPx);
      setProgressHoverSeconds(frac * durationSeconds);
    },
    [durationSeconds]
  );
  const handleProgressBarMouseLeave = React.useCallback(() => {
    setProgressHoverSeconds(null);
    setProgressHoverXPx(null);
  }, []);

  const handleVolumeChange = React.useCallback((value: number) => {
    const el = videoRef.current;
    const v = Math.max(0, Math.min(1, value));
    setVolume(v);
    if (el) {
      el.volume = v;
      el.muted = v === 0;
      setIsMuted(v === 0);
    }
  }, []);
  const handleMuteToggle = React.useCallback(() => {
    const el = videoRef.current;
    if (!el) return;
    if (isMuted) {
      el.muted = false;
      el.volume = volume > 0 ? volume : 1;
      setVolume(el.volume);
      setIsMuted(false);
    } else {
      el.muted = true;
      setIsMuted(true);
    }
  }, [isMuted, volume]);

  React.useEffect(() => {
    const el = videoRef.current;
    if (el) el.playbackRate = playbackSpeed;
  }, [playbackSpeed]);
  React.useEffect(() => {
    try {
      window.localStorage.setItem("workbench_playback_speed", String(playbackSpeed));
    } catch {
      // ignore
    }
  }, [playbackSpeed]);

  const SPEED_CHIPS = [1.0, 1.25, 1.5, 1.75, 2.0] as const;
  const formatSpeedLabel = (speed: number) => {
    if (speed >= 1 && speed < 1.25 && Math.abs(speed - 1) < 0.01) return "1x";
    if (speed >= 1.25 && speed < 1.5 && Math.abs(speed - 1.25) < 0.01) return "1.25x";
    if (speed >= 1.5 && speed < 1.75 && Math.abs(speed - 1.5) < 0.01) return "1.5x";
    if (speed >= 1.75 && speed < 2 && Math.abs(speed - 1.75) < 0.01) return "1.75x";
    if (speed >= 2 && Math.abs(speed - 2) < 0.01) return "2x";
    return `${speed.toFixed(2)}x`;
  };
  const handleSpeedPopoverMouseEnter = React.useCallback(() => {
    if (speedPopoverCloseTimeoutRef.current) {
      window.clearTimeout(speedPopoverCloseTimeoutRef.current);
      speedPopoverCloseTimeoutRef.current = null;
    }
    if (speedPopoverOpenDelayRef.current) return;
    speedPopoverOpenDelayRef.current = window.setTimeout(() => {
      speedPopoverOpenDelayRef.current = null;
      setSpeedPopoverOpen(true);
    }, 250);
  }, []);
  const videoSingleClickTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const videoClickSurfaceRef = React.useRef<HTMLDivElement | null>(null);

  const handleSpeedPopoverMouseLeave = React.useCallback(() => {
    if (speedPopoverOpenDelayRef.current) {
      window.clearTimeout(speedPopoverOpenDelayRef.current);
      speedPopoverOpenDelayRef.current = null;
    }
    speedPopoverCloseTimeoutRef.current = window.setTimeout(() => {
      speedPopoverCloseTimeoutRef.current = null;
      setSpeedPopoverOpen(false);
    }, SPEED_POPOVER_CLOSE_DELAY_MS);
  }, []);
  const cancelSpeedPopoverClose = React.useCallback(() => {
    if (speedPopoverCloseTimeoutRef.current) {
      window.clearTimeout(speedPopoverCloseTimeoutRef.current);
      speedPopoverCloseTimeoutRef.current = null;
    }
  }, []);

  const cycleToNextPlaybackSpeed = React.useCallback(() => {
    setPlaybackSpeed((current) => {
      const idx = SPEED_CHIPS.findIndex((s) => Math.abs(current - s) < 0.01);
      if (idx >= 0) {
        const nextIdx = (idx + 1) % SPEED_CHIPS.length;
        return SPEED_CHIPS[nextIdx];
      }
      const next = SPEED_CHIPS.find((s) => s > current) ?? SPEED_CHIPS[0];
      return next;
    });
  }, []);

  const handleSpeedControlClick = React.useCallback(() => {
    speedControlClickRef.current = true;
    setSpeedPopoverOpen(true);
    cycleToNextPlaybackSpeed();
  }, [cycleToNextPlaybackSpeed]);

  const handleSpeedPopoverOpenChange = React.useCallback((open: boolean) => {
    if (!open && speedControlClickRef.current) {
      speedControlClickRef.current = false;
      return;
    }
    speedControlClickRef.current = false;
    setSpeedPopoverOpen(open);
  }, []);

  const showSeekFeedback = React.useCallback((text: string, side: "left" | "right") => {
    if (seekFeedbackTimeoutRef.current) {
      window.clearTimeout(seekFeedbackTimeoutRef.current);
    }
    setSeekFeedback({ text, side });
    seekFeedbackTimeoutRef.current = window.setTimeout(() => {
      seekFeedbackTimeoutRef.current = null;
      setSeekFeedback(null);
    }, 500);
  }, []);

  const handleVideoSurfaceClick = React.useCallback(() => {
    if (videoSingleClickTimeoutRef.current) return;
    videoSingleClickTimeoutRef.current = window.setTimeout(() => {
      videoSingleClickTimeoutRef.current = null;
      const el = videoRef.current;
      if (el) {
        const icon = el.paused ? "play" : "pause";
        playPauseFeedbackTimeoutsRef.current.forEach(clearTimeout);
        playPauseFeedbackTimeoutsRef.current = [];
        setPlayPauseFeedback(icon);
        setPlayPauseFeedbackVisible(true);
        playPauseFeedbackTimeoutsRef.current.push(
          setTimeout(() => setPlayPauseFeedbackVisible(false), 350)
        );
        playPauseFeedbackTimeoutsRef.current.push(
          setTimeout(() => {
            setPlayPauseFeedback(null);
            playPauseFeedbackTimeoutsRef.current = [];
          }, 650)
        );
      }
      handlePlayPauseToggle();
    }, 250);
  }, [handlePlayPauseToggle]);
  const handleVideoSurfaceDoubleClick = React.useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (videoSingleClickTimeoutRef.current) {
        window.clearTimeout(videoSingleClickTimeoutRef.current);
        videoSingleClickTimeoutRef.current = null;
      }
      const el = videoRef.current;
      const surface = videoClickSurfaceRef.current;
      if (!el || !surface || !Number.isFinite(el.duration)) return;
      const rect = surface.getBoundingClientRect();
      const frac = (event.clientX - rect.left) / rect.width;
      if (frac < 0.25) {
        const newTime = Math.max(0, el.currentTime - 5);
        el.currentTime = newTime;
        setCurrentTimeSeconds(newTime);
        showSeekFeedback("−5 s", "left");
      } else if (frac > 0.75) {
        const newTime = Math.min(el.duration, el.currentTime + 5);
        el.currentTime = newTime;
        setCurrentTimeSeconds(newTime);
        showSeekFeedback("+5 s", "right");
      }
    },
    [showSeekFeedback]
  );

  React.useEffect(() => {
    if (!hasVideoPreview) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = document.activeElement;
      const tagName = target?.tagName?.toLowerCase();
      const isEditable =
        tagName === "input" ||
        tagName === "textarea" ||
        (target as HTMLElement)?.getAttribute?.("contenteditable") === "true";
      if (isEditable) return;

      const el = videoRef.current;
      if (!el) return;

      switch (event.key) {
        case " ":
        case "k":
          event.preventDefault();
          if (el.paused) {
            el.play().catch(() => {});
          } else {
            el.pause();
          }
          break;
        case "ArrowLeft":
          event.preventDefault();
          if (Number.isFinite(el.duration)) {
            const t = Math.max(0, el.currentTime - 5);
            el.currentTime = t;
            setCurrentTimeSeconds(t);
            showSeekFeedback("−5 s", "left");
          }
          break;
        case "ArrowRight":
          event.preventDefault();
          if (Number.isFinite(el.duration)) {
            const t = Math.min(el.duration, el.currentTime + 5);
            el.currentTime = t;
            setCurrentTimeSeconds(t);
            showSeekFeedback("+5 s", "right");
          }
          break;
        case "j":
          event.preventDefault();
          if (Number.isFinite(el.duration)) {
            const t = Math.max(0, el.currentTime - 10);
            el.currentTime = t;
            setCurrentTimeSeconds(t);
            showSeekFeedback("−10 s", "left");
          }
          break;
        case "l":
          event.preventDefault();
          if (Number.isFinite(el.duration)) {
            const t = Math.min(el.duration, el.currentTime + 10);
            el.currentTime = t;
            setCurrentTimeSeconds(t);
            showSeekFeedback("+10 s", "right");
          }
          break;
        case "m":
          event.preventDefault();
          el.muted = !el.muted;
          setIsMuted(el.muted);
          break;
        default:
          break;
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [hasVideoPreview, showSeekFeedback]);

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

  const exportAreaTopBar = hasSubtitles && (
    <div className="flex flex-wrap items-center gap-2">
      {latestOutputPath && !isExporting && (
        <>
          <Button
            variant="secondary"
            size="sm"
            data-testid="workbench-play-export-video"
            onClick={() => void openLatestOutputVideo()}
          >
            Play
          </Button>
          <Button
            variant="secondary"
            size="sm"
            data-testid="workbench-open-export-folder"
            onClick={() => void openLatestOutputFolder()}
          >
            Open folder
          </Button>
        </>
      )}
      {isExporting && (
        <div
          className="flex flex-wrap items-center gap-2"
          data-testid="workbench-export-progress-top"
        >
          <span className="text-xs tabular-nums text-muted-foreground">
            {Math.round(exportProgressPct)}%
          </span>
          <div
            className="w-20 shrink-0"
            title={exportProgressMessage || undefined}
          >
            <Progress value={exportProgressPct} className="h-1.5" />
          </div>
          <Button
            variant="tertiary"
            size="sm"
            data-testid="workbench-cancel-export"
            onClick={() => void cancelExport()}
          >
            Cancel
          </Button>
        </div>
      )}
      <Button
        size="sm"
        data-testid="workbench-export-cta"
        onClick={() => void startExport()}
        disabled={!canExport}
      >
        {latestOutputPath ? "Export again" : "Export"}
      </Button>
    </div>
  );

  if (isLoading) {
    return <WorkbenchSkeleton isNarrow={isNarrow} />;
  }

  return (
    <div data-testid="workbench" className="flex h-full min-h-0 flex-col gap-4">
      <header
        className="flex items-center gap-2 pb-2"
        data-testid="workbench-top-bar"
      >
        <div
          className="flex min-w-0 flex-1 items-center gap-2"
          data-testid="workbench-heading"
        >
          <h1 className="min-w-0 max-w-[min(100%,280px)] truncate text-lg font-semibold tracking-tight text-foreground">
            {title && title !== "Untitled video" ? title : ""}
          </h1>
        </div>
        <div className="min-w-0 flex-1" aria-hidden="true" />
        {hasSubtitles && isNarrow && (
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
        {exportAreaTopBar}
      </header>

      <div className="flex min-h-0 flex-1 flex-col">
      {error ? (
        <div
          className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 py-12"
          data-testid="workbench-backend-error"
        >
          <p className="w-full max-w-md text-center text-sm text-destructive">
            {error}
          </p>
        </div>
      ) : (
        <>
      {showNoSubtitlesState && (
        <section
          className="relative flex min-h-0 flex-1 flex-col items-center rounded-lg border border-border bg-card p-6"
          data-testid="workbench-empty-state"
        >
          <div className="flex w-full max-w-xl flex-1 flex-col justify-center space-y-4 text-center">
            {createSubtitlesError && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {createSubtitlesError}
              </div>
            )}

            {!hasActiveCreateSubtitles &&
            !pendingAutoStartSubtitles &&
            !incomingState?.autoStartSubtitles ? (
              <>
                <p className="text-lg font-semibold text-foreground">No subtitles yet.</p>
                <div className="flex justify-center">
                  <Button
                    data-testid="workbench-create-subtitles"
                    onClick={() => void startCreateSubtitles()}
                  >
                    Create subtitles
                  </Button>
                </div>
              </>
            ) : project?.active_task?.status === "queued" &&
              project?.active_task?.kind === "create_subtitles" ? (
              <>
                <p className="text-lg font-semibold text-foreground">Queued</p>
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
            ) : (() => {
              const at = project?.active_task;
              const heading =
                createSubtitlesHeading ||
                (at?.status === "queued" ? "Queued" : at?.heading) ||
                "Creating subtitles";
              const checklistFromApi =
                at && at.checklist?.length
                  ? buildChecklistFromActiveTask(at)
                  : [];
              const checklistBase =
                createSubtitlesChecklist.length > 0
                  ? createSubtitlesChecklist
                  : checklistFromApi.length > 0
                    ? checklistFromApi
                    : settings
                      ? defaultChecklist(buildGenerateChecklist(settings))
                      : [];
              const checklist = withTimingFallbackChecklist(checklistBase);
              const rawPct =
                isCreatingSubtitles || createSubtitlesProgressPct > 0
                  ? createSubtitlesProgressPct
                  : typeof at?.pct === "number"
                    ? Math.max(0, Math.min(100, at.pct))
                    : 0;
              const pct =
                createSubtitlesStreamHealth !== "open" && rawPct === 100
                  ? 0
                  : rawPct;
              const startedAt =
                createSubtitlesStartedAt ||
                (typeof at?.started_at === "string"
                  ? at.started_at
                  : typeof at?.updated_at === "string"
                    ? at.updated_at
                    : null);
              const elapsedText =
                createSubtitlesElapsedText || formatElapsedSince(startedAt);
              const message =
                createSubtitlesProgressMessage ||
                (typeof at?.message === "string" ? at.message : "");
              return (
                <>
                  <p className="text-lg font-semibold text-foreground">{heading}</p>
                  {checklist.length > 0 && (
                    <Checklist
                      items={checklist}
                      className="text-left"
                      data-testid="workbench-create-checklist"
                    />
                  )}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{Math.round(pct)}%</span>
                      <span
                        title={message || undefined}
                        data-testid="workbench-create-elapsed"
                      >
                        {elapsedText}
                      </span>
                    </div>
                    <Progress value={pct} />
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
              );
            })()}
            {isShortWindow &&
              showElevatorMusicRow &&
              hasActiveCreateSubtitles &&
              !(
                project?.active_task?.status === "queued" &&
                project?.active_task?.kind === "create_subtitles"
              ) && (
                <div
                  className="absolute bottom-4 right-4 animate-in fade-in duration-300"
                  data-testid="workbench-elevator-music-row"
                >
                  <Button
                    variant="secondary"
                    onClick={handleElevatorMusicToggle}
                    className="inline-flex shrink-0 [&_svg]:size-4"
                    aria-label={
                      elevatorMusicPlaying
                        ? "Pause background music"
                        : "Play background music"
                    }
                  >
                    {elevatorMusicPlaying ? (
                      <>
                        <Pause />
                        Pause
                      </>
                    ) : (
                      <>
                        <Play />
                        Some music?
                      </>
                    )}
                  </Button>
                </div>
              )}
          </div>
          {!isShortWindow &&
            showElevatorMusicRow &&
            hasActiveCreateSubtitles &&
            !(
              project?.active_task?.status === "queued" &&
              project?.active_task?.kind === "create_subtitles"
            ) && (
              <div
                className="absolute bottom-6 left-0 right-0 flex justify-center animate-in fade-in duration-300"
                data-testid="workbench-elevator-music-row"
              >
                <div className="flex flex-wrap items-center justify-center gap-3 text-sm text-muted-foreground">
                  <span>Listen to some music while you wait?</span>
                  <Button
                    variant="secondary"
                    onClick={handleElevatorMusicToggle}
                    className="inline-flex shrink-0"
                    aria-label={
                      elevatorMusicPlaying
                        ? "Pause background music"
                        : "Play background music"
                    }
                  >
                    {elevatorMusicPlaying ? (
                      <>
                        <Pause />
                        Pause
                      </>
                    ) : (
                      <>
                        <Play />
                        Play
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
        </section>
      )}

      {!showNoSubtitlesState && (
        <>
          {hasSubtitles && showSubtitlesOverlay && showLeftToggle && (
            <div className="relative z-50 flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={openLeftPanel}
                disabled={isExporting}
                data-testid="workbench-open-left"
              >
                All subtitles
              </Button>
            </div>
          )}

          <div className={cn("flex min-h-0 flex-1 gap-4", isNarrow ? "flex-col" : "flex-row")}>
            <section
              className="flex min-h-[220px] flex-1 items-center justify-center"
              data-testid="workbench-center-panel"
            >
              {hasVideoPreview ? (
                <div
                  ref={videoWrapperRef}
                  className="relative h-full w-full overflow-hidden rounded-md"
                  data-testid="workbench-center-panel-video-wrapper"
                  onMouseEnter={() => setShowVideoControls(true)}
                  onMouseLeave={(e) => {
                    const to = e.relatedTarget;
                    if (to instanceof Node && videoWrapperRef.current?.contains(to)) return;
                    setShowVideoControls(false);
                  }}
                >
                  <video
                    ref={videoRef}
                    className="h-full w-full rounded-md bg-black object-contain dark:bg-muted"
                    src={previewSrc}
                    onPlay={() => {
                      handleVideoPlay();
                      setIsPlaying(true);
                    }}
                    onPause={() => setIsPlaying(false)}
                    onEnded={() => setIsPlaying(false)}
                    onLoadedMetadata={(event) => {
                      const element = event.currentTarget;
                      setCurrentTimeSeconds(element.currentTime || 0);
                      const d = element.duration;
                      setDurationSeconds(
                        Number.isFinite(d) && d >= 0 ? d : 0
                      );
                      setVolume(element.volume);
                      setIsMuted(element.muted);
                      setVideoNaturalSize({
                        width: Math.max(0, Math.round(element.videoWidth || 0)),
                        height: Math.max(0, Math.round(element.videoHeight || 0))
                      });
                    }}
                    onTimeUpdate={(event) =>
                      setCurrentTimeSeconds(event.currentTarget.currentTime || 0)
                    }
                    onSeeked={(event) => setCurrentTimeSeconds(event.currentTarget.currentTime || 0)}
                  />
                  <div
                    ref={videoClickSurfaceRef}
                    className="absolute cursor-default"
                    style={displayedVideoGeometryStyle}
                    onClick={handleVideoSurfaceClick}
                    onDoubleClick={handleVideoSurfaceDoubleClick}
                    onMouseEnter={() => setShowVideoControls(true)}
                    onMouseLeave={(e) => {
                      const to = e.relatedTarget;
                      if (to instanceof Node && (
                        videoControlsBarRef.current?.contains(to) ||
                        subtitleOverlayPositionLayerRef.current?.contains(to)
                      ))
                        return;
                      setShowVideoControls(false);
                    }}
                    aria-hidden
                  />
                  <div
                    className="absolute flex items-center justify-center pointer-events-none"
                    style={displayedVideoGeometryStyle}
                    aria-hidden
                  >
                    <div
                      className={cn(
                        "flex h-20 w-20 items-center justify-center rounded-full bg-black/50 transition-opacity duration-300 ease-out",
                        playPauseFeedbackVisible ? "opacity-100" : "opacity-0"
                      )}
                    >
                      {playPauseFeedback === "play" && (
                        <Play className="h-12 w-12 text-white drop-shadow-md" fill="currentColor" />
                      )}
                      {playPauseFeedback === "pause" && (
                        <Pause className="h-12 w-12 text-white drop-shadow-md" fill="currentColor" />
                      )}
                    </div>
                  </div>
                  <div
                    className={cn("absolute", !isEditingActiveCue && "pointer-events-none")}
                    style={displayedVideoGeometryStyle}
                  >
{SHOW_SUBTITLE_OVERLAY_IN_APP && shouldRenderOverlayImage && (
                        <img
                        className="pointer-events-none absolute inset-0 h-full w-full transition-transform duration-200"
                        src={subtitleOverlaySrc ?? ""}
                        alt="Subtitle preview overlay"
                        data-testid="workbench-subtitle-overlay"
                        style={subtitleControlsPushStyle}
                      />
                    )}
                    {activeCue && (
                      <div
                        ref={subtitleOverlayPositionLayerRef}
                        data-testid="workbench-subtitle-overlay-position-layer"
                        className={cn(
                          "absolute inset-0 flex justify-center",
                          subtitleVerticalClass
                        )}
                        style={subtitleOverlayPositionStyle}
                      >
                        <div
                          className={cn(
                            "pointer-events-none flex min-h-0 min-w-0 flex-1 flex-col items-center",
                            subtitleVerticalJustifyClass
                          )}
                          style={{
                            height: "100%"
                          }}
                        >
                        <div
                          ref={activeSubtitleWrapperRef}
                          className="pointer-events-auto relative z-11 w-fit max-w-full transition-transform duration-200"
                          style={subtitleControlsPushStyle}
                          onMouseEnter={() => {
                            setShowVideoControls(true);
                            setIsHoveringActiveSubtitle(true);
                          }}
                          onMouseLeave={(e) => {
                            const to = e.relatedTarget;
                            setIsHoveringActiveSubtitle(false);
                            if (to instanceof Node && (
                              videoControlsBarRef.current?.contains(to) ||
                              videoClickSurfaceRef.current?.contains(to) ||
                              subtitleOverlayPositionLayerRef.current?.contains(to)
                            ))
                              return;
                            setShowVideoControls(false);
                          }}
                        >
                          <div className="relative w-fit max-w-full">
                            {isEditingActiveCue ? (
                              <div
                                className={cn(
                                  "relative inline-block min-w-16 rounded-md",
                                  !(
                                    appearance.subtitle_mode === "word_highlight" &&
                                    editingWordCount > 0 &&
                                    appearance.background_mode === "line"
                                  ) && "px-3 py-2"
                                )}
                                style={
                                  {
                                    fontFamily:
                                      appearance.font_family || DEFAULT_APPEARANCE.font_family,
                                    ["--subtitle-editor-font"]:
                                      appearance.font_family || DEFAULT_APPEARANCE.font_family
                                  } as React.CSSProperties
                                }
                              >
                                {appearance.subtitle_mode === "word_highlight" &&
                                editingWordCount > 0 ? (
                                  <>
                                    <span
                                      aria-hidden
                                      className="block whitespace-pre-wrap text-center"
                                      dir={subtitleDirection}
                                      style={{
                                        ...subtitlePreviewTextStyle,
                                        fontFamily: "inherit",
                                        unicodeBidi: "plaintext",
                                        color: defaultSubtitleTextColor
                                      }}
                                    >
                                      {(() => {
                                        let seenWordIndex = -1;
                                        return editingSegments.map((segment, idx) => {
                                          const isWord = /\S/.test(segment);
                                          if (isWord) {
                                            seenWordIndex += 1;
                                          }
                                          const isActiveWord =
                                            isWord &&
                                            highlightedWordIndex !== null &&
                                            seenWordIndex === highlightedWordIndex;
                                          if (isActiveWord && hasWordBackground) {
                                            return (
                                              <span
                                                key={`${idx}-${segment}`}
                                                style={{
                                                  position: "relative",
                                                  display: "inline-block",
                                                  color: highlightWordColor
                                                }}
                                              >
                                                <span
                                                  aria-hidden
                                                  style={wordBgBackingStyle}
                                                />
                                                {segment}
                                              </span>
                                            );
                                          }
                                          return (
                                            <span
                                              key={`${idx}-${segment}`}
                                              style={
                                                isActiveWord
                                                  ? { ...activeWordStyle, color: highlightWordColor }
                                                  : { color: defaultSubtitleTextColor }
                                              }
                                            >
                                              {segment}
                                            </span>
                                          );
                                        });
                                      })()}
                                    </span>
                                    <textarea
                                      ref={activeSubtitleRef}
                                      data-testid="workbench-subtitle-editor"
                                      data-workbench-subtitle-editor
                                      className="m-0 absolute inset-0 w-full appearance-none box-border resize-none overflow-hidden rounded-md border-0 bg-transparent px-3 py-2 text-center whitespace-pre-wrap text-transparent caret-white shadow-none transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45"
                                      style={(() => {
                                        const {
                                          fontFamily: _f,
                                          color: _c,
                                          textShadow: _s,
                                          backgroundColor: _bg,
                                          paddingTop: _pt,
                                          paddingRight: _pr,
                                          paddingBottom: _pb,
                                          paddingLeft: _pl,
                                          borderRadius: _br,
                                          ...rest
                                        } = subtitleEditorTextStyle;
                                        return { ...rest, color: "transparent" };
                                      })()}
                                      value={editingText}
                                      onChange={handleEditTextChange}
                                      onKeyDown={handleEditorKeyDown}
                                      rows={1}
                                      wrap="soft"
                                      readOnly={isSavingCue || isExporting}
                                      aria-label="Active subtitle editor"
                                      dir={subtitleDirection}
                                    />
                                  </>
                                ) : (
                                  <>
                                    <span
                                      aria-hidden
                                      className="block whitespace-pre-wrap text-center text-white"
                                      dir={subtitleDirection}
                                      style={{
                                        ...subtitleEditorTextStyle,
                                        fontFamily: "inherit",
                                        visibility: "hidden",
                                        margin: 0,
                                        padding: 0,
                                        border: "none",
                                        boxSizing: "content-box"
                                      }}
                                    >
                                      {editingText || "\u00A0"}
                                    </span>
                                    <textarea
                                      ref={activeSubtitleRef}
                                      data-testid="workbench-subtitle-editor"
                                      data-workbench-subtitle-editor
                                      className="m-0 absolute inset-0 w-full appearance-none box-border resize-none overflow-hidden rounded-md border-0 bg-background/25 px-3 py-2 text-center whitespace-pre-wrap text-white shadow-lg ring-1 ring-primary/45 transition focus-visible:outline-none"
                                      style={(() => {
                                        const { fontFamily: _f, ...rest } =
                                          subtitleEditorTextStyle;
                                        return rest;
                                      })()}
                                      value={editingText}
                                      onChange={handleEditTextChange}
                                      onKeyDown={handleEditorKeyDown}
                                      rows={1}
                                      wrap="soft"
                                      readOnly={isSavingCue || isExporting}
                                      aria-label="Active subtitle editor"
                                      dir={subtitleDirection}
                                    />
                                  </>
                                )}
                              </div>
                            ) : (
                              <div
                                role="button"
                                tabIndex={0}
                                data-testid="workbench-active-subtitle"
                                className={cn(
                                  "m-0 inline-block cursor-text box-border rounded-md border-0 bg-transparent px-3 py-2 text-center text-white shadow-lg transition focus-visible:outline-none hover:bg-background/25 hover:ring-1 hover:ring-primary/45",
                                  isHoveringActiveSubtitle && "bg-background/25 ring-1 ring-primary/45",
                                  isActiveCueSelected
                                    ? "outline-2 outline-offset-2 outline-primary ring-1 ring-primary/50"
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
                                dir={subtitleDirection}
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
                                          if (isActiveWord && hasWordBackground) {
                                            return (
                                              <span
                                                key={`${idx}-${segment}`}
                                                style={{
                                                  position: "relative",
                                                  display: "inline-block",
                                                  color: highlightWordColor
                                                }}
                                              >
                                                <span
                                                  aria-hidden
                                                  style={wordBgBackingStyle}
                                                />
                                                {segment}
                                              </span>
                                            );
                                          }
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
                              <div
                                ref={subtitleEditorControlsRef}
                                data-testid="workbench-subtitle-editor-controls"
                                className={cn(
                                  "absolute z-10 flex items-center justify-end gap-2",
                                  subtitleEditorControlsPlacement === "below"
                                    ? "left-1/2 top-full mt-2 -translate-x-1/2"
                                    : "left-1/2 bottom-full mb-2 -translate-x-1/2"
                                )}
                              >
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
                        </div>
                        </div>
                    )}
                  </div>
                  {seekFeedback && (
                    <div
                      className={cn(
                        "pointer-events-none absolute flex items-center",
                        seekFeedback.side === "left" ? "justify-start pl-6" : "justify-end pr-6"
                      )}
                      style={displayedVideoGeometryStyle}
                    >
                      <span
                        className="text-lg font-medium text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)] animate-in fade-in duration-150"
                        style={{
                          textShadow: "0 0 2px rgba(0,0,0,1), 0 1px 3px rgba(0,0,0,0.9)"
                        }}
                      >
                        {seekFeedback.text}
                      </span>
                    </div>
                  )}
                  <div
                    ref={videoControlsBarRef}
                    className={cn(
                      "flex cursor-default flex-col justify-end rounded-b-md transition-opacity duration-200",
                      showVideoControls ? "opacity-100" : "opacity-0"
                    )}
                    style={{
                      ...videoControlsBarContainerStyle,
                      pointerEvents: showVideoControls ? "auto" : "none"
                    }}
                    data-testid="workbench-video-controls"
                    onMouseEnter={() => setShowVideoControls(true)}
                    onMouseLeave={(e) => {
                      const to = e.relatedTarget;
                      if (to instanceof Node && (
                        videoClickSurfaceRef.current?.contains(to) ||
                        subtitleOverlayPositionLayerRef.current?.contains(to)
                      ))
                        return;
                      setShowVideoControls(false);
                    }}
                  >
                    <div
                      className="flex shrink-0 flex-col justify-center px-3 py-2"
                      style={{
                        minHeight:
                          VIDEO_PROGRESS_HIT_AREA_PY * 2 +
                          VIDEO_PROGRESS_STRIP_HEIGHT_PX_HOVER
                      }}
                    >
                      <div className="relative w-full">
                        <TooltipProvider delayDuration={0}>
                          <Tooltip open={progressHoverSeconds !== null}>
                            <TooltipTrigger asChild>
                              <div
                                className="pointer-events-none absolute top-0 bottom-0 z-0"
                                style={{
                                  left: `${progressHoverXPx ?? lastProgressHoverXPxRef.current}px`,
                                  width: 1,
                                  transform: "translateX(-50%)"
                                }}
                                aria-hidden
                              />
                            </TooltipTrigger>
                            <TooltipContent side="top" sideOffset={4}>
                              {progressHoverSeconds != null
                                ? formatTime(progressHoverSeconds)
                                : ""}
                            </TooltipContent>
                          </Tooltip>
                          <div
                            className="relative flex w-full cursor-pointer items-center justify-center py-4"
                            onClick={handleProgressBarClick}
                            onMouseDown={handleProgressBarMouseDown}
                            onMouseMove={handleProgressBarMouseMove}
                            onMouseLeave={handleProgressBarMouseLeave}
                          >
                            <div
                              ref={progressBarTrackRef}
                              className="relative w-full cursor-pointer rounded-md bg-white/30 transition-[height] duration-150"
                              style={{ height: effectiveProgressStripHeightPx }}
                              role="progressbar"
                              aria-valuenow={durationSeconds > 0 ? currentTimeSeconds : 0}
                              aria-valuemin={0}
                              aria-valuemax={durationSeconds}
                              aria-label="Video progress"
                              data-testid="workbench-video-progress"
                            >
                            {durationSeconds > 0 && progressHoverSeconds !== null && (
                              <div
                                className="absolute inset-y-0 left-0 rounded-l-md bg-white/50"
                                style={{
                                  width: `${(progressHoverSeconds / durationSeconds) * 100}%`
                                }}
                              />
                            )}
                            <div
                              className="absolute inset-y-0 left-0 rounded-l-md bg-primary"
                              style={{
                                width: `${
                                  durationSeconds > 0
                                    ? (currentTimeSeconds / durationSeconds) * 100
                                    : 0
                                }%`
                              }}
                            />
                            {durationSeconds > 0 && (
                              <div
                                className="absolute top-1/2 z-1 rounded-full border-2 border-white bg-primary shadow-md"
                                style={{
                                  left: `${(currentTimeSeconds / durationSeconds) * 100}%`,
                                  width: VIDEO_PROGRESS_THUMB_SIZE_PX,
                                  height: VIDEO_PROGRESS_THUMB_SIZE_PX,
                                  transform: "translate(-50%, -50%)"
                                }}
                              />
                            )}
                          </div>
                          </div>
                        </TooltipProvider>
                      </div>
                    </div>
                    <div
                      className="flex cursor-default items-center gap-2 px-2 py-1.5"
                      style={{
                        height: VIDEO_CONTROL_BAR_HEIGHT_PX,
                        background:
                          "linear-gradient(to top, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.4) 70%, transparent 100%)"
                      }}
                    >
                      <Button
                        type="button"
                        variant="overlay"
                        size="iconSm"
                        onClick={handlePlayPauseToggle}
                        aria-label={isPlaying ? "Pause" : "Play"}
                        data-testid="workbench-video-play-pause"
                      >
                        {isPlaying ? (
                          <Pause fill="currentColor" />
                        ) : (
                          <Play fill="currentColor" />
                        )}
                      </Button>
                      <div className="relative flex items-center gap-0">
                        <Button
                          type="button"
                          variant="overlay"
                          size="iconSm"
                          onClick={handleMuteToggle}
                          aria-label={isMuted ? "Unmute" : "Mute"}
                          data-testid="workbench-video-volume"
                        >
                          {isMuted ? (
                            <VolumeX />
                          ) : (
                            <Volume2 />
                          )}
                        </Button>
                        <div className="w-[100px] shrink-0 cursor-pointer">
                          <Slider
                            className="h-8 w-[100px] shrink-0 cursor-pointer px-1 [&_.bg-primary\\/20]:bg-white/40 [&_.bg-primary]:bg-white [&_.border-primary\\/50]:border-white/80 [&_.bg-background]:bg-white"
                            value={[isMuted ? 0 : volume]}
                            onValueChange={([v]) => handleVolumeChange(v ?? 0)}
                            min={0}
                            max={1}
                            step={0.05}
                          />
                        </div>
                      </div>
                      <span
                        className="ml-4 shrink-0 tabular-nums text-xs font-medium text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)]"
                        style={{ textShadow: "0 0 2px rgba(0,0,0,1), 0 1px 3px rgba(0,0,0,0.9)" }}
                      >
                        {formatTime(currentTimeSeconds)} / {formatTime(durationSeconds)}
                      </span>
                      <div
                        className="flex min-h-[36px] shrink-0 cursor-pointer items-center px-2"
                        onMouseEnter={handleSpeedPopoverMouseEnter}
                        onMouseLeave={handleSpeedPopoverMouseLeave}
                      >
                        <Popover open={speedPopoverOpen} onOpenChange={handleSpeedPopoverOpenChange}>
                          <PopoverTrigger asChild>
                            <Button
                              type="button"
                              variant="overlay"
                              size="sm"
                              className="min-h-9 min-w-9 drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)]"
                              style={{ textShadow: "0 0 2px rgba(0,0,0,1), 0 1px 3px rgba(0,0,0,0.9)" }}
                              aria-label="Playback speed"
                              data-testid="workbench-video-speed"
                              onClick={handleSpeedControlClick}
                            >
                              {formatSpeedLabel(playbackSpeed)}
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent
                            side="top"
                            sideOffset={6}
                            className="w-96 border-border bg-popover p-3 text-popover-foreground"
                            onMouseEnter={cancelSpeedPopoverClose}
                            onMouseLeave={handleSpeedPopoverMouseLeave}
                          >
                            <div className="flex flex-col gap-3">
                              <div className="text-center text-sm font-medium">
                                {playbackSpeed.toFixed(2)}
                              </div>
                              <div className="flex items-center gap-2">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8 shrink-0 rounded-full"
                                  aria-label="Decrease speed"
                                  onClick={() =>
                                    setPlaybackSpeed((s) => Math.max(0.25, Math.round((s - 0.05) * 100) / 100))
                                  }
                                >
                                  <Minus className="h-4 w-4" />
                                </Button>
                                <Slider
                                  className="flex-1 [&_.bg-primary\\/20]:bg-white/40 [&_.bg-primary]:bg-white [&_.border-primary\\/50]:border-white/80 [&_.bg-background]:bg-white"
                                  value={[playbackSpeed]}
                                  onValueChange={([v]) => setPlaybackSpeed(v ?? 1)}
                                  min={0.25}
                                  max={2}
                                  step={0.05}
                                />
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8 shrink-0 rounded-full"
                                  aria-label="Increase speed"
                                  onClick={() =>
                                    setPlaybackSpeed((s) => Math.min(2, Math.round((s + 0.05) * 100) / 100))
                                  }
                                >
                                  <Plus className="h-4 w-4" />
                                </Button>
                              </div>
                              <div className="flex flex-nowrap justify-center gap-1">
                                {SPEED_CHIPS.map((speed) => {
                                  const isSelected = Math.abs(playbackSpeed - speed) < 0.01;
                                  return (
                                    <Button
                                      key={speed}
                                      type="button"
                                      variant={isSelected ? "default" : "secondary"}
                                      size="sm"
                                      className={cn(
                                        "h-7 min-w-16 text-xs",
                                        !isSelected && "hover:bg-accent!"
                                      )}
                                      onClick={() => setPlaybackSpeed(speed)}
                                    >
                                      {speed.toFixed(2)}
                                    </Button>
                                  );
                                })}
                              </div>
                            </div>
                          </PopoverContent>
                        </Popover>
                      </div>
                    </div>
                  </div>
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
              className="fixed inset-0 z-40 bg-overlay-soft"
              onClick={closeOverlays}
              data-testid="workbench-overlay-scrim"
            />
          )}

          {hasSubtitles && showSubtitlesOverlay && leftPanelOpen && (
            <aside
              className="fixed inset-y-0 left-0 z-50 flex w-[min(90vw,360px)] flex-col border-r border-border bg-card shadow"
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
              className="fixed inset-y-0 right-0 z-50 flex w-[min(92vw,360px)] flex-col border-l border-border bg-card shadow"
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

          {false && hasSubtitles && isExporting && (
            <section
              className="rounded-lg border border-border bg-card p-4"
              data-testid="workbench-export-panel"
            >
              {exportError && (
                <div className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                  {exportError}
                </div>
              )}
              {openActionError && (
                <div
                  className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
                  data-testid="workbench-open-action-error"
                >
                  {openActionError}
                </div>
              )}
              <div className="space-y-3">
                <p className="text-sm font-semibold text-foreground">{exportHeading}</p>
                {project?.active_task?.status === "queued" &&
                project?.active_task?.kind === "create_video_with_subtitles" ? (
                  <div className="flex justify-center">
                    <Button
                      variant="secondary"
                      data-testid="workbench-cancel-export"
                      onClick={() => void cancelExport()}
                    >
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <>
                    {exportChecklist.length > 0 && (
                      <Checklist
                        items={exportChecklist}
                        className="text-left"
                        data-testid="workbench-export-checklist"
                      />
                    )}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>{Math.round(exportProgressPct)}%</span>
                        <span
                          title={exportProgressMessage || undefined}
                          data-testid="workbench-export-elapsed"
                        >
                          {exportElapsedText}
                        </span>
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
                  </>
                )}
              </div>
            </section>
          )}
        </>
      )}
        </>
      )}
      </div>
    </div>
  );
};

export default Workbench;
