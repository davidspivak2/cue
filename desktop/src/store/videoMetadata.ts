import { basename } from "@tauri-apps/api/path";

type VideoInfoResponse = {
  duration_seconds: number;
  thumbnail_path: string;
  filename: string;
};

const BACKEND_BASE_URL = "http://127.0.0.1:8765";
const VIDEO_INFO_URL = `${BACKEND_BASE_URL}/video/info`;

export const generateVideoMetadata = async (sourceVideoPath: string, outputDir: string) => {
  const response = await fetch(VIDEO_INFO_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: sourceVideoPath, output_dir: outputDir })
  });
  if (!response.ok) {
    const filename = await basename(sourceVideoPath);
    throw new Error(`Failed to read video metadata for ${filename}`);
  }
  const payload = (await response.json()) as VideoInfoResponse;
  return {
    filename: payload.filename ?? (await basename(sourceVideoPath)),
    durationSeconds: payload.duration_seconds,
    thumbnailPath: payload.thumbnail_path
  };
};
