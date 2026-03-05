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

export type SubtitleStyleAppearance = {
  font_family: string;
  font_size: number;
  font_style: string;
  text_color: string;
  text_opacity: number;
  letter_spacing: number;
  outline_enabled: boolean;
  outline_width: number;
  outline_color: string;
  shadow_enabled: boolean;
  shadow_strength: number;
  shadow_offset_x: number;
  shadow_offset_y: number;
  shadow_color: string;
  shadow_opacity: number;
  shadow_blur: number;
  background_mode: string;
  line_bg_color: string;
  line_bg_opacity: number;
  line_bg_padding: number;
  line_bg_padding_top: number;
  line_bg_padding_right: number;
  line_bg_padding_bottom: number;
  line_bg_padding_left: number;
  line_bg_padding_linked?: boolean;
  line_bg_radius: number;
  word_bg_color: string;
  word_bg_opacity: number;
  word_bg_padding: number;
  word_bg_padding_top: number;
  word_bg_padding_right: number;
  word_bg_padding_bottom: number;
  word_bg_padding_left: number;
  word_bg_padding_linked?: boolean;
  word_bg_radius: number;
  vertical_anchor: string;
  vertical_offset: number;
  position_x?: number;
  position_y?: number;
  subtitle_mode: string;
  highlight_color: string;
};

export type SubtitleStyle = {
  preset: string;
  highlight_color: string;
  highlight_opacity?: number;
  custom?: Partial<SubtitleStyleCustom>;
  appearance?: SubtitleStyleAppearance;
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
  gpu_name?: string | null;
  cpu_cores?: number;
  estimate_5min_sec?: {
    speed?: number;
    auto?: number;
    quality?: number;
    ultra?: number;
  };
  calibration_done?: boolean;
  ultra_available?: boolean;
  ultra_device?: "gpu" | "cpu" | null;
};

export type PreviewStyleRequest = {
  video_path: string;
  srt_path: string;
  timestamp?: number;
  subtitle_style: Partial<SubtitleStyleAppearance>;
  subtitle_mode: string;
  highlight_color: string;
  highlight_opacity: number;
};

export type PreviewStyleResponse = {
  preview_path: string;
  cached?: boolean;
  requested_font_family?: string;
  resolved_font_family?: string;
  font_fallback_used?: boolean;
};

export type PreviewOverlayRequest = {
  width: number;
  height: number;
  subtitle_text: string;
  highlight_word_index?: number | null;
  subtitle_style: Partial<SubtitleStyleAppearance>;
  subtitle_mode: string;
  highlight_color: string;
  highlight_opacity: number;
};

export type PreviewOverlayResponse = {
  overlay_path: string;
  cached?: boolean;
  requested_font_family?: string;
  resolved_font_family?: string;
  font_fallback_used?: boolean;
};

const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const SETTINGS_URL = `${BACKEND_BASE_URL}/settings`;
const DEVICE_URL = `${BACKEND_BASE_URL}/device`;
const PREVIEW_STYLE_URL = `${BACKEND_BASE_URL}/preview-style`;
const PREVIEW_OVERLAY_URL = `${BACKEND_BASE_URL}/preview-overlay`;

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

export const previewStyle = async (
  request: PreviewStyleRequest
): Promise<PreviewStyleResponse> => {
  const response = await fetch(PREVIEW_STYLE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
  await ensureOk(response);
  return (await response.json()) as PreviewStyleResponse;
};

export const previewOverlay = async (
  request: PreviewOverlayRequest
): Promise<PreviewOverlayResponse> => {
  const response = await fetch(PREVIEW_OVERLAY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request)
  });
  await ensureOk(response);
  return (await response.json()) as PreviewOverlayResponse;
};
