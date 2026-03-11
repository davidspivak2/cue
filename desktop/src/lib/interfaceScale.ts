export const INTERFACE_SCALE_OPTIONS = [
  { value: 1, label: "100%" },
  { value: 1.1, label: "110%" },
  { value: 1.25, label: "125%" },
  { value: 1.5, label: "150%" }
] as const;

export type InterfaceScaleValue =
  (typeof INTERFACE_SCALE_OPTIONS)[number]["value"];

export const DEFAULT_INTERFACE_SCALE: InterfaceScaleValue = 1;

const INTERFACE_SCALE_STORAGE_KEY = "cue_interface_scale_v1";
const INTERFACE_SCALE_CHANGE_EVENT = "cue:interface-scale-change";

export type InterfaceScaleChangeSource =
  | "backend-sync"
  | "settings"
  | "shortcut";

export const normalizeInterfaceScale = (value: unknown): InterfaceScaleValue => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return DEFAULT_INTERFACE_SCALE;
  }
  const matchingOption = INTERFACE_SCALE_OPTIONS.find(
    (option) => Math.abs(option.value - value) < 0.001
  );
  return matchingOption?.value ?? DEFAULT_INTERFACE_SCALE;
};

export const getInterfaceScaleIndex = (value: unknown): number => {
  const normalized = normalizeInterfaceScale(value);
  return INTERFACE_SCALE_OPTIONS.findIndex((option) => option.value === normalized);
};

export const getInterfaceScaleLabel = (value: unknown): string => {
  const option = INTERFACE_SCALE_OPTIONS[getInterfaceScaleIndex(value)];
  return option?.label ?? "100%";
};

export const readStoredInterfaceScale = (): InterfaceScaleValue => {
  if (typeof window === "undefined") {
    return DEFAULT_INTERFACE_SCALE;
  }
  const raw = window.localStorage.getItem(INTERFACE_SCALE_STORAGE_KEY);
  return normalizeInterfaceScale(raw == null ? NaN : Number(raw));
};

export const writeStoredInterfaceScale = (value: unknown) => {
  if (typeof window === "undefined") {
    return;
  }
  const normalized = normalizeInterfaceScale(value);
  window.localStorage.setItem(INTERFACE_SCALE_STORAGE_KEY, String(normalized));
};

export const applyInterfaceScale = (value: unknown) => {
  if (typeof document === "undefined") {
    return;
  }
  const normalized = normalizeInterfaceScale(value);
  document.documentElement.style.setProperty("--app-scale", String(normalized));
};

export const setLocalInterfaceScale = (
  value: unknown,
  source: InterfaceScaleChangeSource
): InterfaceScaleValue => {
  const normalized = normalizeInterfaceScale(value);
  applyInterfaceScale(normalized);
  writeStoredInterfaceScale(normalized);
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent(INTERFACE_SCALE_CHANGE_EVENT, {
        detail: { scale: normalized, source }
      })
    );
  }
  return normalized;
};

export const subscribeToInterfaceScaleChanges = (
  listener: (scale: InterfaceScaleValue, source: InterfaceScaleChangeSource) => void
) => {
  if (typeof window === "undefined") {
    return () => {};
  }
  const handler = (
    event: Event
  ) => {
    const detail = (event as CustomEvent<{
      scale: InterfaceScaleValue;
      source: InterfaceScaleChangeSource;
    }>).detail;
    if (!detail) {
      return;
    }
    listener(detail.scale, detail.source);
  };
  window.addEventListener(INTERFACE_SCALE_CHANGE_EVENT, handler);
  return () => {
    window.removeEventListener(INTERFACE_SCALE_CHANGE_EVENT, handler);
  };
};

export const stepInterfaceScale = (
  value: unknown,
  direction: -1 | 1
): InterfaceScaleValue => {
  const currentIndex = getInterfaceScaleIndex(value);
  const nextIndex = Math.max(
    0,
    Math.min(currentIndex + direction, INTERFACE_SCALE_OPTIONS.length - 1)
  );
  return INTERFACE_SCALE_OPTIONS[nextIndex]?.value ?? DEFAULT_INTERFACE_SCALE;
};

export const initializeInterfaceScale = () => {
  applyInterfaceScale(readStoredInterfaceScale());
};
