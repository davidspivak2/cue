const WINDOWS_DRIVE_PATH_RE = /^[A-Za-z]:[\\/]/;
const WINDOWS_FILE_URL_PATH_RE = /^\/[A-Za-z]:\//;

export const normalizeLocalPath = (value: string): string => {
  if (!value || !value.startsWith("file://")) {
    return value;
  }

  try {
    const url = new URL(value);
    const decodedPath = decodeURIComponent(url.pathname || "");
    if (!decodedPath) {
      return value;
    }
    if (WINDOWS_FILE_URL_PATH_RE.test(decodedPath)) {
      return decodedPath.slice(1).replace(/\//g, "\\");
    }
    return decodedPath;
  } catch {
    const stripped = value.replace(/^file:\/+/, "");
    if (WINDOWS_DRIVE_PATH_RE.test(stripped)) {
      return stripped.replace(/\//g, "\\");
    }
    return stripped;
  }
};
