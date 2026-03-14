import { convertFileSrc } from "@tauri-apps/api/core";

import { normalizeLocalPath } from "@/lib/normalizeLocalPath";

const BACKEND_BASE_URL = "http://127.0.0.1:8765";

export const buildLocalFileUrl = (path: string): string => {
  const normalizedPath = normalizeLocalPath(path);
  return `${BACKEND_BASE_URL}/local-file?path=${encodeURIComponent(normalizedPath)}`;
};

export const resolveLocalFileUrl = (
  path: string | null | undefined,
  useTauri: boolean
): string => {
  if (!path) {
    return "";
  }
  const normalizedPath = normalizeLocalPath(path);
  if (useTauri) {
    const pathForTauri = normalizedPath.replace(/\\/g, "/");
    return convertFileSrc(pathForTauri);
  }
  return buildLocalFileUrl(normalizedPath);
};
