import * as React from "react";
import { useTheme } from "next-themes";
import { Laptop, Moon, Sun, Rabbit, Crosshair } from "lucide-react";

import EngineSkeletonLoader from "@/components/EngineSkeletonLoader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useCalibration } from "@/contexts/CalibrationContext";
import { useDeviceInfo } from "@/contexts/DeviceInfoContext";
import { useSettings } from "@/contexts/SettingsContext";
import { fetchSettings, SettingsConfig, updateSettings } from "@/settingsClient";
import {
  BACKEND_UNREACHABLE_MESSAGE,
  isBackendUnreachableError,
  messageForBackendError,
  waitForBackendHealthy
} from "@/backendHealth";

type DeepPartial<T> = {
  [K in keyof T]?: T[K] extends Record<string, unknown> ? DeepPartial<T[K]> : T[K];
};

const mergeDeep = <T,>(base: T, update: DeepPartial<T>): T => {
  const next: Record<string, unknown> = { ...(base as Record<string, unknown>) };
  Object.entries(update || {}).forEach(([key, value]) => {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      next[key] &&
      typeof next[key] === "object" &&
      !Array.isArray(next[key])
    ) {
      next[key] = mergeDeep(next[key], value as DeepPartial<unknown>);
    } else {
      next[key] = value as unknown;
    }
  });
  return next as T;
};

const TRANSCRIPTION_QUALITY_OPTIONS: ReadonlyArray<{
  value: "speed" | "auto" | "quality" | "ultra";
}> = [
  { value: "speed" },
  { value: "auto" },
  { value: "quality" },
  { value: "ultra" }
];

function getDefaultTranscriptionQuality(gpuAvailable: boolean | null): "quality" | "auto" {
  return gpuAvailable === true ? "quality" : "auto";
}

function getQualityDisplayLabel(
  value: "speed" | "auto" | "quality" | "ultra",
  ultraAvailable: boolean,
  isDefault = false
): string {
  let label: string;
  switch (value) {
    case "speed":
      label = "Fastest transcription";
      break;
    case "auto":
      label = "Balanced speed and accuracy";
      break;
    case "quality":
      label = ultraAvailable ? "Better accuracy" : "Maximum accuracy";
      break;
    case "ultra":
      label = "Maximum accuracy";
      break;
    default:
      label = "Balanced speed and accuracy";
  }
  return isDefault ? `${label} (default)` : label;
}

function getQualityOption(value: "speed" | "auto" | "quality" | "ultra") {
  return TRANSCRIPTION_QUALITY_OPTIONS.find((o) => o.value === value);
}

function getQualityNerdsLine(
  value: "speed" | "auto" | "quality" | "ultra",
  gpuAvailable: boolean | null,
  ultraDevice?: "gpu" | "cpu" | null
): string {
  if (value === "ultra") {
    if (ultraDevice === "gpu") return "Runs on GPU (float32).";
    if (ultraDevice === "cpu") return "Runs on CPU (float32).";
    return "Checking...";
  }
  if (gpuAvailable === null) {
    return "Checking...";
  }
  if (value === "speed") {
    return gpuAvailable ? "Runs on GPU (int8)." : "Runs on CPU (int8).";
  }
  if (value === "auto") {
    return gpuAvailable ? "Runs on GPU (int8_float16)." : "Runs on CPU (int16).";
  }
  return gpuAvailable ? "Runs on GPU (float16)." : "Runs on CPU (float32).";
}

function formatEstimate5Min(sec: number): string {
  const min = sec / 60;
  const label =
    min < 10 ? (min % 1 === 0 ? `${min}` : min.toFixed(1)) : `${Math.round(min)}`;
  return `Est. ~${label} min per 5 min of video.`;
}

function getDisplayEstimateSec(
  est: { quality?: number; ultra?: number; [k: string]: number | undefined },
  selectedValue: string
): number | undefined {
  const raw = est[selectedValue];
  if (raw == null) return undefined;
  if (
    selectedValue === "ultra" &&
    est.quality != null &&
    est.ultra != null &&
    est.quality === est.ultra
  ) {
    return Math.round(est.quality * 1.5);
  }
  return raw;
}

const SettingsSection = ({
  title,
  children,
  sectionClassName
}: {
  title: string;
  children: React.ReactNode;
  sectionClassName?: string;
}) => (
  <section
    className={`rounded-lg border border-border bg-card p-6 shadow-[var(--shadow-card)] ${sectionClassName ?? ""}`}
  >
    <h2 className="text-lg font-semibold text-foreground">{title}</h2>
    <div className="mt-4 space-y-3">{children}</div>
  </section>
);

const DIAGNOSTICS_CATEGORIES = [
  { key: "app_system", label: "Include app and system info" },
  { key: "video_info", label: "Include video file info" },
  { key: "audio_info", label: "Include audio (WAV) info" },
  { key: "transcription_config", label: "Include transcription settings" },
  { key: "srt_stats", label: "Include SRT stats" },
  { key: "commands_timings", label: "Include commands and run times" }
] as const;

const Settings = () => {
  const { theme, setTheme } = useTheme();
  const { diagnosticsSectionVisible } = useSettings();

  const [settings, setSettings] = React.useState<SettingsConfig | null>(null);
  const settingsRef = React.useRef<SettingsConfig | null>(null);
  settingsRef.current = settings;
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isBackendStarting, setIsBackendStarting] = React.useState(true);
  const deviceInfo = useDeviceInfo();
  const { isCalibrating, calibrationPct } = useCalibration();
  const gpuAvailable = deviceInfo?.gpu_available ?? null;
  const ultraAvailable = deviceInfo?.ultra_available === true;
  const ultraDevice = deviceInfo?.ultra_device ?? null;
  const calibrationDone = Boolean(deviceInfo?.calibration_done);
  const showUltra = ultraAvailable && ultraDevice === "gpu";
  const steps = React.useMemo(
    (): ReadonlyArray<"speed" | "auto" | "quality" | "ultra"> =>
      showUltra
        ? (["speed", "auto", "quality", "ultra"] as const)
        : ultraAvailable
          ? (["speed", "auto", "quality"] as const)
          : (["speed", "auto"] as const),
    [showUltra, ultraAvailable]
  );
  const defaultQuality = getDefaultTranscriptionQuality(gpuAvailable);
  const storedQuality = settings?.transcription_quality ?? defaultQuality;
  const effectiveQuality = steps.includes(
    storedQuality as (typeof steps)[number]
  )
    ? storedQuality
    : (steps[steps.length - 1] as typeof storedQuality);
  const sliderIndex = (() => {
    const i = steps.indexOf(
      effectiveQuality === "ultra" ? "ultra" : effectiveQuality
    );
    return i >= 0 ? i : Math.min(0, steps.length - 1);
  })();
  const downgradeUltraPersistedRef = React.useRef(false);
  const saveFolderInputRef = React.useRef<HTMLInputElement>(null);
  const [saveFolderTruncated, setSaveFolderTruncated] = React.useState(false);
  const savePolicy = settings?.save_policy ?? "same_folder";
  const saveFolderValue = settings?.save_folder ?? "";

  React.useEffect(() => {
    let active = true;
    const run = async () => {
      try {
        setIsBackendStarting(true);
        await waitForBackendHealthy();
        if (!active) {
          return;
        }
        setIsBackendStarting(false);
        const data = await fetchSettings();
        if (active) {
          setSettings(data);
          setError(null);
        }
      } catch (err) {
        if (active) {
          setError(
            isBackendUnreachableError(err)
              ? BACKEND_UNREACHABLE_MESSAGE
              : err instanceof Error
                ? err.message
                : "Failed to load settings."
          );
        }
      } finally {
        if (active) {
          setIsBackendStarting(false);
          setIsLoading(false);
        }
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, []);

  const persistSettings = React.useCallback(
    async (update: DeepPartial<SettingsConfig>) => {
      if (!settings) {
        return;
      }
      const optimistic = mergeDeep(settings, update);
      setSettings(optimistic);
      try {
        const next = await updateSettings(update as Record<string, unknown>);
        setSettings(next);
      } catch (err) {
        setError(messageForBackendError(err, err instanceof Error ? err.message : "Failed to save settings."));
        setSettings(settings);
      }
    },
    [settings]
  );

  React.useEffect(() => {
    if (
      !settings ||
      downgradeUltraPersistedRef.current ||
      steps.includes(storedQuality as (typeof steps)[number])
    ) {
      return;
    }
    downgradeUltraPersistedRef.current = true;
    void persistSettings({
      transcription_quality: steps[steps.length - 1]
    });
  }, [settings, storedQuality, steps, persistSettings]);

  const openFolderDialog = React.useCallback(async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false });
      if (typeof selected === "string" && settings) {
        await persistSettings({ save_folder: selected, save_policy: "fixed_folder" });
      }
    } catch {
      // Ignore dialog errors outside Tauri.
    }
  }, [settings, persistSettings]);

  const handleSavePolicyChange = async (value: string) => {
    await persistSettings({ save_policy: value });
    if (value === "fixed_folder") {
      await openFolderDialog();
    }
  };

  const handleBrowseFolder = async () => {
    if (!settings || settings.save_policy !== "fixed_folder") {
      return;
    }
    await openFolderDialog();
  };

  React.useEffect(() => {
    if (savePolicy !== "fixed_folder" || !saveFolderValue) {
      setSaveFolderTruncated(false);
      return;
    }
    const el = saveFolderInputRef.current;
    if (!el) {
      return;
    }
    let rafId: number;
    let timeoutId: ReturnType<typeof setTimeout>;
    let ro: ResizeObserver | null = null;
    const check = () => {
      try {
        if (el.isConnected && el.scrollWidth > el.clientWidth) {
          setSaveFolderTruncated(true);
        } else {
          setSaveFolderTruncated(false);
        }
      } catch {
        setSaveFolderTruncated(false);
      }
    };
    rafId = requestAnimationFrame(() => {
      check();
      timeoutId = setTimeout(check, 100);
      try {
        ro = new ResizeObserver(() => {
          requestAnimationFrame(check);
        });
        ro.observe(el);
      } catch {
        setSaveFolderTruncated(false);
      }
    });
    return () => {
      cancelAnimationFrame(rafId);
      clearTimeout(timeoutId);
      ro?.disconnect();
    };
  }, [savePolicy, saveFolderValue]);

  React.useEffect(() => {
    return () => {
      const current = settingsRef.current;
      if (current?.save_policy === "fixed_folder" && !current?.save_folder) {
        void updateSettings({ save_policy: "same_folder" });
      }
    };
  }, []);

  if (isLoading) {
    return <EngineSkeletonLoader variant="settings" />;
  }

  if (!settings) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-destructive">{error ?? "Settings unavailable."}</p>
        <Button type="button" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  const diagnosticsEnabled = settings.diagnostics?.enabled ?? false;

  return (
    <div className="flex flex-col gap-4 pb-6" data-testid="settings-content">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <SettingsSection title="Transcription quality" sectionClassName="pb-4">
        <div className="space-y-3">
          {steps.length === 2 ? (
            (() => {
              const safeIndex = Math.max(0, Math.min(sliderIndex, steps.length - 1));
              const selectedValue = steps[safeIndex];
              const showEstimate =
                calibrationDone &&
                selectedValue &&
                deviceInfo?.estimate_5min_sec?.[selectedValue] != null;
              return (
                <div className="flex flex-col items-start gap-2 mt-5">
                  <ToggleGroup
                    type="single"
                    variant="outline"
                    value={selectedValue}
                    onValueChange={(v) => v && persistSettings({ transcription_quality: v })}
                    className="inline-flex"
                    data-testid="transcription-quality-slider"
                    aria-label="Transcription quality"
                  >
                    <ToggleGroupItem value="speed" aria-label="Faster" className="gap-1.5">
                      <Rabbit className="h-4 w-4 shrink-0" aria-hidden />
                      Faster
                    </ToggleGroupItem>
                    <ToggleGroupItem value="auto" aria-label="Accurate" className="gap-1.5">
                      <Crosshair className="h-4 w-4 shrink-0" aria-hidden />
                      Accurate
                    </ToggleGroupItem>
                  </ToggleGroup>
                  <div
                    id="transcription-quality-description"
                    className="text-sm text-muted-foreground space-y-0.5"
                    role="status"
                    aria-live="polite"
                  >
                    {!calibrationDone && isCalibrating && (
                      <p className="text-xs text-muted-foreground">
                        Estimating transcription time… {calibrationPct}%
                      </p>
                    )}
                    {showEstimate && selectedValue && (
                      <p className="text-xs">
                        {formatEstimate5Min(
                          getDisplayEstimateSec(
                            deviceInfo!.estimate_5min_sec!,
                            selectedValue
                          )!
                        )}
                      </p>
                    )}
                    <p className="text-xs">
                      For nerds:{" "}
                      {getQualityNerdsLine(
                        selectedValue,
                        gpuAvailable,
                        ultraDevice
                      )}
                    </p>
                  </div>
                </div>
              );
            })()
          ) : (
            <>
              {(() => {
                const safeIndex = Math.max(0, Math.min(sliderIndex, steps.length - 1));
                const selectedValue = steps[safeIndex];
                const option = selectedValue ? getQualityOption(selectedValue) : null;
                const showEstimate =
                  calibrationDone &&
                  selectedValue &&
                  deviceInfo?.estimate_5min_sec?.[selectedValue] != null;
                return option ? (
                  <div className="flex flex-col items-start gap-0.5 mt-5 text-left">
                    <p
                      id="transcription-quality-description"
                      className="text-sm font-medium text-foreground"
                    >
                      {getQualityDisplayLabel(
                        option.value,
                        showUltra,
                        option.value === defaultQuality
                      )}
                    </p>
                    <div className="text-xs text-muted-foreground" role="status" aria-live="polite">
                      {!calibrationDone && isCalibrating && (
                        <p className="mt-0.5">Estimating transcription time… {calibrationPct}%</p>
                      )}
                      {showEstimate && selectedValue && (
                        <p className="mt-0.5">
                          {formatEstimate5Min(
                            getDisplayEstimateSec(
                              deviceInfo!.estimate_5min_sec!,
                              selectedValue
                            )!
                          )}
                        </p>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      For nerds:{" "}
                      {getQualityNerdsLine(
                        selectedValue,
                        gpuAvailable,
                        ultraDevice
                      )}
                    </p>
                  </div>
                ) : null;
              })()}
              <div className="flex w-full flex-col gap-3 mt-5">
                <div className="w-full px-1.5">
                  <Slider
                    data-testid="transcription-quality-slider"
                    aria-label="Transcription quality"
                    aria-describedby="transcription-quality-description"
                    value={[sliderIndex]}
                    onValueChange={([v]) => {
                      const idx = typeof v === "number" ? v : 0;
                      const clamped = Math.max(0, Math.min(idx, steps.length - 1));
                      persistSettings({
                        transcription_quality: steps[clamped]
                      });
                    }}
                    min={0}
                    max={steps.length - 1}
                    step={1}
                    stops={steps.length}
                    hideRange
                    thumbEdgeOffset={5}
                    className="w-full"
                  />
                </div>
                <div className="flex w-full justify-between text-muted-foreground">
                  <div className="flex flex-col items-start">
                    <Rabbit className="h-5 w-5" aria-hidden />
                    <span className="text-sm font-medium text-foreground mt-0.5">Faster</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <Crosshair className="h-5 w-5" aria-hidden />
                    <span className="text-sm font-medium text-foreground mt-0.5 text-right">Accurate</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </SettingsSection>

      <SettingsSection title="Transcription options">
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="punctuation-rescue">Improve punctuation</Label>
              <p className="text-xs text-muted-foreground">
                If subtitles come out with little or no punctuation, Cue will retry
                transcription in a compatibility mode. This can take longer.
              </p>
            </div>
            <Switch
              id="punctuation-rescue"
              checked={settings.punctuation_rescue_fallback_enabled}
              onCheckedChange={(checked) =>
                persistSettings({ punctuation_rescue_fallback_enabled: Boolean(checked) })
              }
            />
          </div>
          <div className="flex items-start justify-between gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="audio-filter">Clean up audio before transcription</Label>
              <p className="text-xs text-muted-foreground">
                May help noisy recordings, but can reduce punctuation.
              </p>
            </div>
            <Switch
              id="audio-filter"
              checked={settings.apply_audio_filter}
              onCheckedChange={(checked) =>
                persistSettings({ apply_audio_filter: Boolean(checked) })
              }
            />
          </div>
        </div>
      </SettingsSection>

      <SettingsSection title="Save subtitled videos to">
        <div className="space-y-3">
          <RadioGroup
            value={savePolicy}
            onValueChange={handleSavePolicyChange}
            className="space-y-2"
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem id="save-same" value="same_folder" />
              <Label htmlFor="save-same">Same folder as the video</Label>
            </div>
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <RadioGroupItem id="save-fixed" value="fixed_folder" />
                <Label htmlFor="save-fixed">Specific folder</Label>
              </div>
              {savePolicy === "fixed_folder" && (
                <div className="flex gap-2 pl-6">
                  <TooltipProvider delayDuration={200}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="min-w-0 flex-1">
                          <Input
                            ref={saveFolderInputRef}
                            placeholder="No folder selected"
                            value={saveFolderValue}
                            readOnly
                            className="bg-muted cursor-default truncate focus-visible:ring-0"
                          />
                        </div>
                      </TooltipTrigger>
                      {saveFolderValue ? (
                        <TooltipContent
                          side="top"
                          sideOffset={4}
                          className="z-200 max-w-[min(90vw,28rem)] break-all"
                        >
                          {saveFolderValue}
                        </TooltipContent>
                      ) : null}
                    </Tooltip>
                  </TooltipProvider>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleBrowseFolder}
                  >
                    Browse...
                  </Button>
                </div>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem id="save-ask" value="ask_every_time" />
              <Label htmlFor="save-ask">Ask every time</Label>
            </div>
          </RadioGroup>
        </div>
      </SettingsSection>

      <SettingsSection title="Theme">
        <div className="space-y-2">
          <ToggleGroup
            type="single"
            variant="outline"
            value={theme ?? "system"}
            onValueChange={(v) => v && setTheme(v)}
            className="inline-flex"
          >
            <ToggleGroupItem value="light" aria-label="Light">
              <Sun className="mr-2 size-4" />
              Light
            </ToggleGroupItem>
            <ToggleGroupItem value="dark" aria-label="Dark">
              <Moon className="mr-2 size-4" />
              Dark
            </ToggleGroupItem>
            <ToggleGroupItem value="system" aria-label="System">
              <Laptop className="mr-2 size-4" />
              System
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </SettingsSection>

      {diagnosticsSectionVisible && (
        <div data-testid="settings-diagnostics-section">
          <SettingsSection title="Diagnostics">
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <Label htmlFor="diagnostics-enabled">Save diagnostics</Label>
                <Switch
                  id="diagnostics-enabled"
                  checked={diagnosticsEnabled}
                  onCheckedChange={(checked) =>
                    persistSettings({ diagnostics: { enabled: Boolean(checked) } })
                  }
                />
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-sm"
                  onClick={() =>
                    persistSettings({
                      keep_extracted_audio: true,
                      diagnostics: {
                        enabled: true,
                        archive_on_exit: true,
                        write_on_success: true,
                        render_timing_logs_enabled: true,
                        categories: {
                          app_system: true,
                          video_info: true,
                          audio_info: true,
                          transcription_config: true,
                          srt_stats: true,
                          commands_timings: true
                        }
                      }
                    })
                  }
                >
                  Turn all on
                </Button>
                <span className="text-muted-foreground">·</span>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-sm"
                  onClick={() =>
                    persistSettings({
                      keep_extracted_audio: false,
                      diagnostics: {
                        enabled: false,
                        archive_on_exit: false,
                        write_on_success: false,
                        render_timing_logs_enabled: false,
                        categories: {
                          app_system: false,
                          video_info: false,
                          audio_info: false,
                          transcription_config: false,
                          srt_stats: false,
                          commands_timings: false
                        }
                      }
                    })
                  }
                >
                  Turn all off
                </Button>
              </div>
              <div className="space-y-3 pt-1">
                <p className="text-xs font-medium text-muted-foreground">When</p>
                <div className="flex items-center justify-between gap-4">
                  <Label htmlFor="diagnostics-archive">Zip logs when app closes</Label>
                  <Switch
                    id="diagnostics-archive"
                    checked={settings.diagnostics?.archive_on_exit}
                    onCheckedChange={(checked) =>
                      persistSettings({
                        diagnostics: { archive_on_exit: Boolean(checked) }
                      })
                    }
                    disabled={!diagnosticsEnabled}
                  />
                </div>
                <div className="flex items-center justify-between gap-4">
                  <Label htmlFor="diagnostics-success">
                    Also save when jobs succeed
                  </Label>
                  <Switch
                    id="diagnostics-success"
                    checked={settings.diagnostics?.write_on_success}
                    onCheckedChange={(checked) =>
                      persistSettings({
                        diagnostics: { write_on_success: Boolean(checked) }
                      })
                    }
                    disabled={!diagnosticsEnabled}
                  />
                </div>
                <div className="flex items-center justify-between gap-4">
                  <Label htmlFor="diagnostics-render">Save render timing logs</Label>
                  <Switch
                    id="diagnostics-render"
                    checked={settings.diagnostics?.render_timing_logs_enabled ?? false}
                    onCheckedChange={(checked) =>
                      persistSettings({
                        diagnostics: { render_timing_logs_enabled: Boolean(checked) }
                      })
                    }
                    disabled={!diagnosticsEnabled}
                  />
                </div>
                <div className="flex items-center justify-between gap-4">
                  <Label htmlFor="diagnostics-keep-wav">Keep extracted WAV file</Label>
                  <Switch
                    id="diagnostics-keep-wav"
                    checked={settings.keep_extracted_audio}
                    onCheckedChange={(checked) =>
                      persistSettings({ keep_extracted_audio: Boolean(checked) })
                    }
                    disabled={!diagnosticsEnabled}
                  />
                </div>
              </div>
              <div className="space-y-3 pt-2">
                <p className="text-xs font-medium text-muted-foreground">
                  What to include
                </p>
                {DIAGNOSTICS_CATEGORIES.map((category) => (
                  <div
                    key={category.key}
                    className="flex items-center justify-between gap-4"
                  >
                    <Label htmlFor={`diagnostics-${category.key}`}>
                      {category.label}
                    </Label>
                    <Switch
                      id={`diagnostics-${category.key}`}
                      checked={
                        settings.diagnostics?.categories?.[
                          category.key as keyof typeof settings.diagnostics.categories
                        ]
                      }
                      onCheckedChange={(checked) =>
                        persistSettings({
                          diagnostics: {
                            categories: { [category.key]: Boolean(checked) }
                          }
                        })
                      }
                      disabled={!diagnosticsEnabled}
                    />
                  </div>
                ))}
              </div>
            </div>
          </SettingsSection>
        </div>
      )}
    </div>
  );
};

export default Settings;
