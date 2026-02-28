import * as React from "react";
import { useTheme } from "next-themes";
import { Laptop, Moon, Sun } from "lucide-react";

import EngineSkeletonLoader from "@/components/EngineSkeletonLoader";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "@/components/ui/tooltip";
import {
  fetchDeviceInfo,
  fetchSettings,
  SettingsConfig,
  updateSettings
} from "@/settingsClient";
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

const qualityOptions = [
  { value: "auto", label: "Auto" },
  { value: "fast", label: "Fast (int8)" },
  { value: "accurate", label: "Accurate (int16)" },
  { value: "ultra", label: "Ultra accurate (float32)" }
];

const qualityHelperText = (quality: string) => {
  if (quality === "ultra") {
    return "Very slow on most CPUs. Use only if you need maximum accuracy.";
  }
  if (quality === "fast") {
    return "Faster, but may reduce accuracy on some machines.";
  }
  return "";
};

const qualityRunSummary = (quality: string, gpuAvailable: boolean | null) => {
  if (quality === "fast") {
    return "This will run on: CPU (int8)";
  }
  if (quality === "accurate") {
    return "This will run on: CPU (int16)";
  }
  if (quality === "ultra") {
    return "This will run on: CPU (float32)";
  }
  if (gpuAvailable === null) {
    return "Checking GPU...";
  }
  return gpuAvailable ? "This will run on: GPU" : "This will run on: CPU";
};

const SettingsSection = ({
  title,
  children
}: {
  title: string;
  children: React.ReactNode;
}) => (
  <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
    <h2 className="text-lg font-semibold text-foreground">{title}</h2>
    <div className="mt-4 space-y-3">{children}</div>
  </section>
);

const Settings = () => {
  const { theme, setTheme } = useTheme();

  const [settings, setSettings] = React.useState<SettingsConfig | null>(null);
  const settingsRef = React.useRef<SettingsConfig | null>(null);
  settingsRef.current = settings;
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isBackendStarting, setIsBackendStarting] = React.useState(true);
  const [gpuAvailable, setGpuAvailable] = React.useState<boolean | null>(null);
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

  React.useEffect(() => {
    let active = true;
    fetchDeviceInfo()
      .then((data) => {
        if (active) {
          setGpuAvailable(Boolean(data?.gpu_available));
        }
      })
      .catch(() => {
        if (active) {
          setGpuAvailable(null);
        }
      });
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

      <SettingsSection title="Transcription quality">
        <div className="space-y-2">
          <div className="max-w-xs">
            <Select
              value={settings.transcription_quality}
              onValueChange={(value) => persistSettings({ transcription_quality: value })}
            >
              <SelectTrigger id="transcription-quality">
                <SelectValue placeholder="Select quality" />
              </SelectTrigger>
              <SelectContent>
                {qualityOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <p className="text-sm text-muted-foreground">
            {qualityRunSummary(settings.transcription_quality, gpuAvailable)}
          </p>
          {qualityHelperText(settings.transcription_quality) ? (
            <p className="text-sm text-muted-foreground">
              {qualityHelperText(settings.transcription_quality)}
            </p>
          ) : null}
        </div>
      </SettingsSection>

      <SettingsSection title="Save subtitles to">
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

      <div data-testid="settings-diagnostics-section">
        <SettingsSection title="Diagnostics">
          <div className="flex items-start gap-2">
            <Checkbox
              id="diagnostics-archive"
              checked={settings.diagnostics?.archive_on_exit}
              onCheckedChange={(checked) =>
                persistSettings({
                  diagnostics: { archive_on_exit: Boolean(checked) }
                })
              }
              disabled={!diagnosticsEnabled}
            />
            <Label htmlFor="diagnostics-archive">Zip logs and outputs on exit</Label>
          </div>
          <div className="flex items-start gap-2">
            <Checkbox
              id="diagnostics-enabled"
              checked={diagnosticsEnabled}
              onCheckedChange={(checked) =>
                persistSettings({ diagnostics: { enabled: Boolean(checked) } })
              }
            />
            <Label htmlFor="diagnostics-enabled">Enable diagnostics logging</Label>
          </div>
          <div className="flex items-start gap-2">
            <Checkbox
              id="diagnostics-success"
              checked={settings.diagnostics?.write_on_success}
              onCheckedChange={(checked) =>
                persistSettings({
                  diagnostics: { write_on_success: Boolean(checked) }
                })
              }
              disabled={!diagnosticsEnabled}
            />
            <Label htmlFor="diagnostics-success">
              Write diagnostics on successful completion
            </Label>
          </div>
          <div className="flex items-start gap-2">
            <Checkbox
              id="diagnostics-render"
              checked={settings.diagnostics?.render_timing_logs_enabled ?? false}
              onCheckedChange={(checked) =>
                persistSettings({
                  diagnostics: { render_timing_logs_enabled: Boolean(checked) }
                })
              }
              disabled={!diagnosticsEnabled}
            />
            <Label htmlFor="diagnostics-render">Enable render timing logs (dev-only)</Label>
          </div>
          <div className="mt-2 space-y-2">
            {[
              { key: "app_system", label: "App + system info" },
              { key: "video_info", label: "Video info" },
              { key: "audio_info", label: "Audio (WAV) info" },
              { key: "transcription_config", label: "Transcription config" },
              { key: "srt_stats", label: "SRT stats" },
              { key: "commands_timings", label: "Commands + timings" }
            ].map((category) => (
              <div key={category.key} className="flex items-start gap-2">
                <Checkbox
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
                <Label htmlFor={`diagnostics-${category.key}`}>{category.label}</Label>
              </div>
            ))}
          </div>
        </SettingsSection>
      </div>
    </div>
  );
};

export default Settings;
