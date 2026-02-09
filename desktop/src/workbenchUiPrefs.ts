export type WorkbenchUiPrefs = {
  leftPanelOpen: boolean;
  leftPanelWidth: number;
};

const PREFS_KEY = "cue_workbench_ui_prefs_v1";
const MIN_WIDTH = 280;
const MAX_WIDTH = 480;
const DEFAULT_WIDTH = 360;

const clampWidth = (value: number) => Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, value));

const parsePrefs = (raw: string | null): Record<string, WorkbenchUiPrefs> => {
  if (!raw) {
    return {};
  }
  try {
    const parsed = JSON.parse(raw) as Record<string, WorkbenchUiPrefs>;
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    return parsed;
  } catch {
    return {};
  }
};

export const getWorkbenchPrefs = (projectId: string): WorkbenchUiPrefs => {
  if (!projectId) {
    return { leftPanelOpen: false, leftPanelWidth: DEFAULT_WIDTH };
  }
  const prefs = parsePrefs(localStorage.getItem(PREFS_KEY));
  const entry = prefs[projectId];
  if (!entry) {
    return { leftPanelOpen: false, leftPanelWidth: DEFAULT_WIDTH };
  }
  return {
    leftPanelOpen: Boolean(entry.leftPanelOpen),
    leftPanelWidth: clampWidth(Number(entry.leftPanelWidth ?? DEFAULT_WIDTH))
  };
};

export const setWorkbenchPrefs = (projectId: string, updates: Partial<WorkbenchUiPrefs>) => {
  if (!projectId) {
    return;
  }
  const prefs = parsePrefs(localStorage.getItem(PREFS_KEY));
  const current = prefs[projectId] ?? { leftPanelOpen: false, leftPanelWidth: DEFAULT_WIDTH };
  const next: WorkbenchUiPrefs = {
    leftPanelOpen:
      updates.leftPanelOpen === undefined ? current.leftPanelOpen : updates.leftPanelOpen,
    leftPanelWidth: clampWidth(
      updates.leftPanelWidth === undefined ? current.leftPanelWidth : updates.leftPanelWidth
    )
  };
  prefs[projectId] = next;
  localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
};

export const workbenchWidthLimits = {
  min: MIN_WIDTH,
  max: MAX_WIDTH,
  default: DEFAULT_WIDTH
};
