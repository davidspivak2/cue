export type DiagnosticsCategories = {
  app_system: boolean;
  video_info: boolean;
  audio_info: boolean;
  transcription_config: boolean;
  srt_stats: boolean;
  commands_timings: boolean;
};

export type DiagnosticsSettings = {
  enabled: boolean;
  write_on_success: boolean;
  archive_on_exit: boolean;
  categories: DiagnosticsCategories;
  render_timing_logs_enabled?: boolean;
};

export type SubtitleStyleCustom = {
  font_family: string;
  font_size: number;
  text_color: string;
  outline: number;
  shadow: number;
  margin_v: number;
  box_enabled: boolean;
  box_opacity: number;
  box_padding: number;
};

export type SubtitleStyle = {
  preset: string;
  highlight_color: string;
  highlight_opacity?: number;
  custom?: Partial<SubtitleStyleCustom>;
  appearance?: Record<string, unknown>;
};

export type SettingsConfig = {
  save_policy: string;
  save_folder?: string;
  transcription_quality: string;
  punctuation_rescue_fallback_enabled: boolean;
  apply_audio_filter: boolean;
  keep_extracted_audio: boolean;
  diagnostics: DiagnosticsSettings;
  subtitle_mode: string;
  subtitle_style: SubtitleStyle;
};

export type DeviceInfo = {
  gpu_available: boolean;
};

const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const SETTINGS_URL = `${BACKEND_BASE_URL}/settings`;
const DEVICE_URL = `${BACKEND_BASE_URL}/device`;

const ensureOk = async (response: Response) => {
  if (response.ok) {
    return;
  }
  const text = await response.text();
  throw new Error(text || `Request failed: ${response.status}`);
};

export const fetchSettings = async (): Promise<SettingsConfig> => {
  const response = await fetch(SETTINGS_URL);
  await ensureOk(response);
  return (await response.json()) as SettingsConfig;
};

export const updateSettings = async (
  update: Record<string, unknown>
): Promise<SettingsConfig> => {
  const response = await fetch(SETTINGS_URL, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ settings: update })
  });
  await ensureOk(response);
  return (await response.json()) as SettingsConfig;
};

export const fetchDeviceInfo = async (): Promise<DeviceInfo> => {
  const response = await fetch(DEVICE_URL);
  await ensureOk(response);
  return (await response.json()) as DeviceInfo;
};
