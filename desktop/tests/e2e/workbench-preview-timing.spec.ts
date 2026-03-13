import { expect, test } from "@playwright/test";

import type { SrtCue } from "../../src/lib/srt";
import {
  resolveHighlightWordIndexFromTimings,
  type ProjectWordTimingCue
} from "../../src/lib/workbenchPreviewTiming";

const buildCue = (overrides: Partial<SrtCue> = {}): SrtCue => ({
  id: "cue-1",
  index: 1,
  startSeconds: 10,
  endSeconds: 14,
  text: "one two three",
  ...overrides
});

const buildCueTiming = (overrides: Partial<ProjectWordTimingCue> = {}): ProjectWordTimingCue => ({
  cue_index: 0,
  cue_start: 10,
  cue_end: 14,
  cue_text: "one two three",
  words: [
    { text: "one", start: 10.2, end: 10.7, confidence: 0.9 },
    { text: "two", start: 10.8, end: 11.3, confidence: 0.9 },
    { text: "three", start: 11.4, end: 12.0, confidence: 0.9 }
  ],
  ...overrides
});

test.describe("workbench preview timing helper", () => {
  test("uses absolute timings when fresh word timings are available", () => {
    const cue = buildCue();
    const cueTiming = buildCueTiming();

    expect(resolveHighlightWordIndexFromTimings(cue, 10.1, cueTiming)).toBeNull();
    expect(resolveHighlightWordIndexFromTimings(cue, 10.25, cueTiming)).toBe(0);
    expect(resolveHighlightWordIndexFromTimings(cue, 10.95, cueTiming)).toBe(1);
    expect(resolveHighlightWordIndexFromTimings(cue, 11.6, cueTiming)).toBe(2);
  });

  test("supports cue-relative timing artifacts without changing current fallback behavior", () => {
    const cue = buildCue();
    const cueTiming = buildCueTiming({
      words: [
        { text: "one", start: 0.1, end: 0.6, confidence: 0.9 },
        { text: "two", start: 0.7, end: 1.1, confidence: 0.9 },
        { text: "three", start: 1.2, end: 1.7, confidence: 0.9 }
      ]
    });

    expect(resolveHighlightWordIndexFromTimings(cue, 10.05, cueTiming)).toBeNull();
    expect(resolveHighlightWordIndexFromTimings(cue, 10.15, cueTiming)).toBe(0);
    expect(resolveHighlightWordIndexFromTimings(cue, 10.75, cueTiming)).toBe(1);
    expect(resolveHighlightWordIndexFromTimings(cue, 11.25, cueTiming)).toBe(2);
  });

  test("returns null when timings are missing or stale and Workbench has no usable cue timing", () => {
    const cue = buildCue();

    expect(resolveHighlightWordIndexFromTimings(cue, 10.8, undefined)).toBeNull();
  });

  test("returns null when timing artifacts are incomplete and no valid spans remain", () => {
    const cue = buildCue();
    const cueTiming = buildCueTiming({
      words: [
        { text: "one", start: Number.NaN, end: 10.7, confidence: 0.9 },
        { text: "two", start: 10.8, end: Number.NaN, confidence: 0.9 }
      ]
    });

    expect(resolveHighlightWordIndexFromTimings(cue, 10.9, cueTiming)).toBeNull();
  });

  test("ignores extra timing entries beyond the visible cue word count", () => {
    const cue = buildCue({ text: "one two" });
    const cueTiming = buildCueTiming({
      words: [
        { text: "one", start: 10.2, end: 10.7, confidence: 0.9 },
        { text: "two", start: 10.8, end: 11.3, confidence: 0.9 },
        { text: "three", start: 11.4, end: 12.0, confidence: 0.9 }
      ]
    });

    expect(resolveHighlightWordIndexFromTimings(cue, 11.6, cueTiming)).toBe(1);
  });
});
