const DEFAULT_SHADOW_UI_ANGLE = 145;
const MIN_DISTANCE = 0;
const OFFSET_PRECISION = 1000;
const ZERO_EPSILON = 0.0005;

export type ShadowUiPolar = {
  angle: number;
  distance: number;
  hasVisibleOffset: boolean;
};

const normalizeAngle = (value: number) => {
  if (!Number.isFinite(value)) {
    return DEFAULT_SHADOW_UI_ANGLE;
  }
  const normalized = ((value % 360) + 360) % 360;
  return normalized === 360 ? 0 : normalized;
};

const roundOffset = (value: number) => {
  const rounded = Math.round(value * OFFSET_PRECISION) / OFFSET_PRECISION;
  return Math.abs(rounded) < ZERO_EPSILON ? 0 : rounded;
};

export const shadowOffsetsToUiPolar = (
  offsetX: number,
  offsetY: number
): ShadowUiPolar => {
  const distance = Math.hypot(offsetX, offsetY);
  if (distance < ZERO_EPSILON) {
    return {
      angle: DEFAULT_SHADOW_UI_ANGLE,
      distance: 0,
      hasVisibleOffset: false
    };
  }

  const screenAngle = normalizeAngle((Math.atan2(offsetY, offsetX) * 180) / Math.PI);
  return {
    angle: normalizeAngle(screenAngle + 90),
    distance,
    hasVisibleOffset: true
  };
};

export const shadowUiPolarToOffsets = (distance: number, angle: number) => {
  const normalizedDistance = Math.max(
    MIN_DISTANCE,
    Number.isFinite(distance) ? distance : MIN_DISTANCE
  );
  if (normalizedDistance < ZERO_EPSILON) {
    return {
      shadow_offset_x: 0,
      shadow_offset_y: 0
    };
  }

  const screenAngle = normalizeAngle(angle - 90);
  const radians = (screenAngle * Math.PI) / 180;
  return {
    shadow_offset_x: roundOffset(normalizedDistance * Math.cos(radians)),
    shadow_offset_y: roundOffset(normalizedDistance * Math.sin(radians))
  };
};

export const clampShadowUiAngle = (value: number) =>
  Math.min(359, Math.max(0, Math.round(normalizeAngle(value))));

export const clampShadowDistance = (value: number) =>
  Math.max(MIN_DISTANCE, Math.round(Math.max(MIN_DISTANCE, value) * 10) / 10);

export const DEFAULT_SHADOW_UI_ANGLE_DEGREES = DEFAULT_SHADOW_UI_ANGLE;
