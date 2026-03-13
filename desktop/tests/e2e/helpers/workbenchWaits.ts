import { expect, type Locator } from "@playwright/test";

type SizedRect = {
  width: number;
  height: number;
};

export type RectSnapshot = SizedRect & {
  top: number;
  left: number;
  right?: number;
  bottom?: number;
};

type PreviewLayerReadyOptions = {
  layer: Locator;
  readRect: (layer: Locator) => Promise<SizedRect>;
  prepare?: () => Promise<void>;
  minimumWidth?: number;
  minimumHeight?: number;
  timeout?: number;
};

type RectStabilityOptions = {
  timeout?: number;
  settleWindowMs?: number;
  tolerancePx?: number;
};

const RECT_KEYS = ["top", "left", "right", "bottom", "width", "height"] as const;

const measureMaxRectDelta = (previous: RectSnapshot, current: RectSnapshot) =>
  RECT_KEYS.reduce((maxDelta, key) => {
    const previousValue = previous[key];
    const currentValue = current[key];
    if (typeof previousValue !== "number" || typeof currentValue !== "number") {
      return maxDelta;
    }
    return Math.max(maxDelta, Math.abs(currentValue - previousValue));
  }, 0);

export const waitForWorkbenchPreviewLayerReady = async ({
  layer,
  readRect,
  prepare,
  minimumWidth = 10,
  minimumHeight = 10,
  timeout = 2000
}: PreviewLayerReadyOptions) => {
  await expect(layer).toHaveCount(1);

  const initialRect = await readRect(layer);
  if (
    prepare &&
    (initialRect.width <= minimumWidth || initialRect.height <= minimumHeight)
  ) {
    await prepare();
  }

  await expect
    .poll(async () => {
      const rect = await readRect(layer);
      return rect.width > minimumWidth && rect.height > minimumHeight;
    }, { timeout })
    .toBe(true);

  return layer;
};

export const waitForOpacityAtLeast = async (
  readOpacity: () => Promise<number>,
  minimumOpacity = 0.95,
  timeout = 1200
) => {
  await expect.poll(readOpacity, { timeout }).toBeGreaterThan(minimumOpacity);
};

export const waitForOpacityAtMost = async (
  readOpacity: () => Promise<number>,
  maximumOpacity = 0.05,
  timeout = 1200
) => {
  await expect.poll(readOpacity, { timeout }).toBeLessThan(maximumOpacity);
};

export const waitForRectStability = async (
  readRect: () => Promise<RectSnapshot>,
  { timeout = 1200, settleWindowMs = 220, tolerancePx = 1.5 }: RectStabilityOptions = {}
) => {
  let previousRect: RectSnapshot | null = null;
  let stableSinceMs: number | null = null;

  await expect
    .poll(async () => {
      const currentRect = await readRect();
      const maxDelta =
        previousRect === null ? Number.POSITIVE_INFINITY : measureMaxRectDelta(previousRect, currentRect);
      previousRect = currentRect;

      if (maxDelta <= tolerancePx) {
        stableSinceMs ??= Date.now();
      } else {
        stableSinceMs = null;
      }

      return stableSinceMs !== null && Date.now() - stableSinceMs >= settleWindowMs;
    }, { timeout })
    .toBe(true);
};
