export type SrtCue = {
  id: string;
  index: number;
  startSeconds: number;
  endSeconds: number;
  text: string;
};

const TIMESTAMP_RE =
  /(?<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?<end>\d{2}:\d{2}:\d{2},\d{3})/;

const parseTimestamp = (value: string): number | null => {
  const parts = value.replace(",", ".").split(":");
  if (parts.length !== 3) {
    return null;
  }
  const hours = Number(parts[0]);
  const minutes = Number(parts[1]);
  const seconds = Number(parts[2]);
  if (!Number.isFinite(hours) || !Number.isFinite(minutes) || !Number.isFinite(seconds)) {
    return null;
  }
  return hours * 3600 + minutes * 60 + seconds;
};

const formatTimestamp = (seconds: number): string => {
  const clamped = Math.max(0, seconds);
  const totalMs = Math.round(clamped * 1000);
  const hours = Math.floor(totalMs / 3_600_000);
  const minutes = Math.floor((totalMs % 3_600_000) / 60_000);
  const secs = Math.floor((totalMs % 60_000) / 1000);
  const millis = totalMs % 1000;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(
    secs
  ).padStart(2, "0")},${String(millis).padStart(3, "0")}`;
};

export const parseSrt = (srtText: string): SrtCue[] => {
  const normalized = srtText.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!normalized) {
    return [];
  }

  const blocks = normalized.split(/\n\s*\n/);
  const cues: SrtCue[] = [];
  for (const block of blocks) {
    const lines = block
      .split("\n")
      .map((line) => line.trimEnd())
      .filter((line) => line.trim().length > 0);
    if (lines.length === 0) {
      continue;
    }

    let timestampLineIndex = -1;
    let match: RegExpMatchArray | null = null;
    for (let idx = 0; idx < lines.length; idx += 1) {
      const candidate = lines[idx].match(TIMESTAMP_RE);
      if (candidate) {
        timestampLineIndex = idx;
        match = candidate;
        break;
      }
    }
    if (!match || timestampLineIndex < 0) {
      continue;
    }

    const start = match.groups?.start;
    const end = match.groups?.end;
    if (!start || !end) {
      continue;
    }

    const startSeconds = parseTimestamp(start);
    const endSeconds = parseTimestamp(end);
    if (startSeconds === null || endSeconds === null) {
      continue;
    }

    const explicitIndex = Number(lines[0]);
    const cueIndex =
      Number.isInteger(explicitIndex) && explicitIndex > 0 ? explicitIndex : cues.length + 1;
    const textLines = lines.slice(timestampLineIndex + 1);
    const text = textLines.join("\n").trim();

    cues.push({
      id: `${cueIndex}-${startSeconds}-${endSeconds}-${cues.length}`,
      index: cueIndex,
      startSeconds,
      endSeconds,
      text
    });
  }
  return cues;
};

export const serializeSrt = (cues: SrtCue[]): string => {
  const lines: string[] = [];
  cues.forEach((cue, idx) => {
    const cueIndex = Number.isInteger(cue.index) && cue.index > 0 ? cue.index : idx + 1;
    lines.push(String(cueIndex));
    lines.push(`${formatTimestamp(cue.startSeconds)} --> ${formatTimestamp(cue.endSeconds)}`);
    lines.push(cue.text.trim());
    lines.push("");
  });
  return `${lines.join("\n").trimEnd()}\n`;
};
