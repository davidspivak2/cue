import * as React from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import StyleControls from "@/components/SubtitleStyle/StyleControls";
import {
  fetchSettings,
  previewStyle,
  updateSettings,
  SubtitleStyleAppearance
} from "@/settingsClient";

/* ---------- types ---------- */

export type ReviewLocationState = {
  videoPath: string;
  srtPath: string;
  outputDir: string;
  previewFramePath?: string | null;
};

const SESSION_KEY = "cue_review_state";

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

/* ---------- hooks ---------- */

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

/* ---------- component ---------- */

const Review = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const isTauriEnv = isTauri();

  /* ── resolve navigation state ── */
  const routerState = location.state as ReviewLocationState | null;
  const [navState, setNavState] = React.useState<ReviewLocationState | null>(
    routerState
  );

  React.useEffect(() => {
    if (routerState) {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(routerState));
      setNavState(routerState);
    } else {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (saved) {
        try {
          setNavState(JSON.parse(saved) as ReviewLocationState);
        } catch {
          navigate("/", { replace: true });
        }
      } else {
        navigate("/", { replace: true });
      }
    }
  }, [routerState, navigate]);

  /* ── settings state ── */
  const [appearance, setAppearance] =
    React.useState<SubtitleStyleAppearance>(DEFAULT_APPEARANCE);
  const customAppearanceRef = React.useRef<SubtitleStyleAppearance>(DEFAULT_APPEARANCE);
  const [preset, setPreset] = React.useState("Default");
  const [highlightOpacity, setHighlightOpacity] = React.useState(1.0);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  /* ── preview state ── */
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = React.useState(false);

  /* ── load settings on mount ── */
  React.useEffect(() => {
    let active = true;
    fetchSettings()
      .then((data) => {
        if (!active) return;
        const style = data.subtitle_style;
        const app =
          (style.appearance as SubtitleStyleAppearance | undefined) ??
          DEFAULT_APPEARANCE;
        setAppearance({
          ...DEFAULT_APPEARANCE,
          ...app,
          subtitle_mode: data.subtitle_mode ?? app.subtitle_mode,
          highlight_color: style.highlight_color ?? app.highlight_color
        });
        const resolvedPreset = style.preset ?? "Default";
        setPreset(resolvedPreset);
        if (resolvedPreset === "Custom") {
          customAppearanceRef.current = {
            ...DEFAULT_APPEARANCE,
            ...app,
            subtitle_mode: data.subtitle_mode ?? app.subtitle_mode,
            highlight_color: style.highlight_color ?? app.highlight_color
          };
        }
        setHighlightOpacity(style.highlight_opacity ?? 1.0);
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof Error ? err.message : "Failed to load settings."
          );
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  /* ── set initial preview from navigation state ── */
  React.useEffect(() => {
    if (navState?.previewFramePath && isTauriEnv) {
      setPreviewUrl(convertFileSrc(navState.previewFramePath));
    }
  }, [navState, isTauriEnv]);

  /* ── request backend preview ── */
  const requestPreview = React.useCallback(
    async (app: SubtitleStyleAppearance, hlOpacity: number) => {
      if (!navState) return;
      setPreviewLoading(true);
      try {
        const result = await previewStyle({
          video_path: navState.videoPath,
          srt_path: navState.srtPath,
          subtitle_style: app,
          subtitle_mode: app.subtitle_mode,
          highlight_color: app.highlight_color,
          highlight_opacity: hlOpacity
        });
        if (isTauriEnv && result.preview_path) {
          setPreviewUrl(convertFileSrc(result.preview_path));
        }
      } catch {
        /* preview error is non-fatal — keep showing last preview */
      } finally {
        setPreviewLoading(false);
      }
    },
    [navState, isTauriEnv]
  );

  const debouncedPreview = useDebounce(
    (app: SubtitleStyleAppearance, hlOpacity: number) => {
      requestPreview(app, hlOpacity);
    },
    150
  );

  /* ── persist settings (slower debounce) ── */
  const persistSettings = React.useCallback(
    async (
      app: SubtitleStyleAppearance,
      presetName: string,
      hlOpacity: number
    ) => {
      try {
        await updateSettings({
          subtitle_mode: app.subtitle_mode,
          subtitle_style: {
            preset: presetName,
            highlight_color: app.highlight_color,
            highlight_opacity: hlOpacity,
            appearance: app as unknown as Record<string, unknown>
          }
        });
      } catch {
        /* silent — settings saved on export as safety net */
      }
    },
    []
  );

  const debouncedPersist = useDebounce(
    (
      app: SubtitleStyleAppearance,
      presetName: string,
      hlOpacity: number
    ) => {
      persistSettings(app, presetName, hlOpacity);
    },
    500
  );

  /* ── request initial backend preview once settings are loaded ── */
  const initialPreviewDone = React.useRef(false);
  React.useEffect(() => {
    if (!isLoading && navState && !initialPreviewDone.current) {
      initialPreviewDone.current = true;
      requestPreview(appearance, highlightOpacity);
    }
  }, [isLoading, navState, appearance, highlightOpacity, requestPreview]);

  /* ── handlers ── */
  const handleAppearanceChange = (
    changes: Partial<SubtitleStyleAppearance>
  ) => {
    setAppearance((prev) => {
      const next = { ...prev, ...changes };
      customAppearanceRef.current = next;
      debouncedPreview(next, highlightOpacity);
      debouncedPersist(next, preset, highlightOpacity);
      return next;
    });
    if (preset !== "Custom") {
      setPreset("Custom");
    }
  };

  const handlePresetChange = (newPreset: string) => {
    if (preset === "Custom") {
      customAppearanceRef.current = appearance;
    }
    const nextAppearance =
      newPreset === "Custom"
        ? { ...customAppearanceRef.current }
        : applyPresetAppearance(appearance, newPreset);
    setPreset(newPreset);
    setAppearance(nextAppearance);
    debouncedPersist(nextAppearance, newPreset, highlightOpacity);
    debouncedPreview(nextAppearance, highlightOpacity);
  };

  const handleHighlightOpacityChange = (opacity: number) => {
    setHighlightOpacity(opacity);
    debouncedPreview(appearance, opacity);
    debouncedPersist(appearance, preset, opacity);
  };

  const handleResetPreset = () => {
    /* Persist the current preset to trigger backend normalization,
       then reload settings to get the canonical defaults. */
    persistSettings(appearance, preset, highlightOpacity).then(() => {
      fetchSettings().then((data) => {
        const style = data.subtitle_style;
        const app =
          (style.appearance as SubtitleStyleAppearance | undefined) ??
          DEFAULT_APPEARANCE;
        setAppearance({
          ...DEFAULT_APPEARANCE,
          ...app,
          subtitle_mode: data.subtitle_mode ?? app.subtitle_mode,
          highlight_color: style.highlight_color ?? app.highlight_color
        });
        requestPreview(
          {
            ...DEFAULT_APPEARANCE,
            ...app,
            subtitle_mode: data.subtitle_mode ?? app.subtitle_mode,
            highlight_color: style.highlight_color ?? app.highlight_color
          },
          highlightOpacity
        );
      });
    });
  };

  /* ── export ── */
  const [exporting, setExporting] = React.useState(false);

  const handleExport = async () => {
    if (!navState) return;
    setExporting(true);
    try {
      /* save style first */
      await updateSettings({
        subtitle_mode: appearance.subtitle_mode,
        subtitle_style: {
          preset,
          highlight_color: appearance.highlight_color,
          highlight_opacity: highlightOpacity,
          appearance: appearance as unknown as Record<string, unknown>
        }
      });
      /* navigate to Home with export action */
      navigate("/legacy", {
        state: {
          action: "start_export",
          videoPath: navState.videoPath,
          srtPath: navState.srtPath,
          outputDir: navState.outputDir
        }
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save settings."
      );
      setExporting(false);
    }
  };

  /* ── early returns ── */
  if (!navState) {
    return null; /* will redirect in useEffect */
  }

  if (isLoading) {
    return (
      <p className="text-sm text-muted-foreground">Loading style settings...</p>
    );
  }

  /* ── render ── */
  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col gap-4">
      {/* Header */}
      <header className="flex items-center justify-between">
        <Button
          asChild
          variant="ghost"
          size="sm"
          className="gap-2"
          onClick={(e) => {
            e.preventDefault();
            navigate("/");
          }}
        >
          <span>
            <ArrowLeft className="h-4 w-4" />
            Back
          </span>
        </Button>
        <h1 className="text-lg font-semibold">Review subtitles</h1>
        <Button onClick={handleExport} disabled={exporting} size="sm">
          {exporting ? (
            <>
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              Saving...
            </>
          ) : (
            "Export"
          )}
        </Button>
      </header>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Main content — responsive: stacked on narrow, side-by-side on wide */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row">
        {/* Preview panel */}
        <div className="flex items-start justify-center lg:flex-1">
          <div className="relative w-full overflow-hidden rounded-lg border border-border bg-muted">
            <div style={{ aspectRatio: "16 / 9" }} className="relative">
              {previewUrl ? (
                <img
                  src={previewUrl}
                  alt="Subtitle preview"
                  className="h-full w-full object-contain"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  Preview not available
                </div>
              )}
              {previewLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-background/30">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Controls panel */}
        <div className="flex min-h-0 w-full flex-col lg:w-80 lg:shrink-0 xl:w-96">
          <Tabs defaultValue="style" className="flex min-h-0 flex-1 flex-col">
            <TabsList className="shrink-0">
              <TabsTrigger value="style">Style</TabsTrigger>
              <TabsTrigger value="edit" disabled>
                Edit
              </TabsTrigger>
            </TabsList>

            <TabsContent
              value="style"
              className="mt-3 min-h-0 flex-1"
            >
              <ScrollArea className="h-full pr-3">
                <StyleControls
                  appearance={appearance}
                  preset={preset}
                  highlightOpacity={highlightOpacity}
                  onAppearanceChange={handleAppearanceChange}
                  onPresetChange={handlePresetChange}
                  onHighlightOpacityChange={handleHighlightOpacityChange}
                  onResetPreset={handleResetPreset}
                />
              </ScrollArea>
            </TabsContent>

            <TabsContent value="edit" className="mt-3">
              <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border p-8 text-center">
                <p className="text-sm font-medium text-muted-foreground">
                  Subtitle text editing
                </p>
                <p className="text-xs text-muted-foreground">
                  Coming soon — you&apos;ll be able to edit individual subtitle lines here.
                </p>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default Review;
