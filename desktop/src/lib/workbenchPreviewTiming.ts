import type { ProjectWordTimingsDocument } from "@/projectsClient";
import type { SrtCue } from "@/lib/srt";

export type ProjectWordTimingCue = ProjectWordTimingsDocument["cues"][number];

export const resolveHighlightWordIndexFromTimings = (
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
      a.startSeconds === b.startSeconds
        ? a.endSeconds - b.endSeconds
        : a.startSeconds - b.startSeconds
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
