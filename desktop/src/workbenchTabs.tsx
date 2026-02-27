import * as React from "react";
import { useLocation, useNavigate } from "react-router-dom";

export const HOME_TAB_ID = "home" as const;
export type ActiveView = typeof HOME_TAB_ID | string;

export type WorkbenchTab = {
  projectId: string;
  title: string;
  path?: string;
  /** Used in title bar icon-only (narrow) mode. Resolved from project manifest or ProjectHub list. */
  thumbnail_path?: string | null;
};

const PERSIST_KEY = "cue_title_bar_tabs";
type PersistedTabs = {
  projectIds: string[];
  lastActiveProjectId: string | typeof HOME_TAB_ID;
  /** Optional per-tab meta so tab titles and paths survive restart. Keyed by projectId. */
  tabMeta?: Record<string, { title?: string; path?: string }>;
};

type WorkbenchTabsContextValue = {
  tabs: WorkbenchTab[];
  /** Currently active view: Home or a projectId. Synced from route. */
  activeView: ActiveView;
  /** Set active view (e.g. when user clicks Home or a tab). Persistence uses this. */
  setActiveView: (view: ActiveView) => void;
  openOrActivateTab: (tab: WorkbenchTab) => void;
  ensureTab: (tab: WorkbenchTab) => void;
  /**
   * Close a video tab. If it was the active tab, calls onSwitchTo(next) with
   * the adjacent tab (prefer left; if leftmost, right) or 'home' if it was the last video tab.
   */
  closeTab: (projectId: string, onSwitchTo?: (next: ActiveView) => void) => void;
  updateTabMeta: (projectId: string, updates: Partial<WorkbenchTab>) => void;
  /** Reorder video tabs to match the given projectId order. Persistence updates automatically. */
  reorderTabs: (orderedProjectIds: string[]) => void;
};

const WorkbenchTabsContext = React.createContext<WorkbenchTabsContextValue | null>(null);

const upsertTab = (tabs: WorkbenchTab[], nextTab: WorkbenchTab): WorkbenchTab[] => {
  const index = tabs.findIndex((tab) => tab.projectId === nextTab.projectId);
  if (index === -1) {
    return [...tabs, nextTab];
  }
  const current = tabs[index];
  const merged = { ...current, ...nextTab };
  const nextTabs = [...tabs];
  nextTabs[index] = merged;
  return nextTabs;
};

function loadPersisted(): PersistedTabs | null {
  try {
    const raw = localStorage.getItem(PERSIST_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as PersistedTabs;
    if (!Array.isArray(data.projectIds) || typeof data.lastActiveProjectId !== "string") {
      return null;
    }
    const tabMeta =
      data.tabMeta && typeof data.tabMeta === "object" && !Array.isArray(data.tabMeta)
        ? data.tabMeta
        : undefined;
    return {
      projectIds: data.projectIds.filter((id): id is string => typeof id === "string"),
      lastActiveProjectId:
        data.lastActiveProjectId === HOME_TAB_ID ? HOME_TAB_ID : data.lastActiveProjectId,
      tabMeta,
    };
  } catch {
    return null;
  }
}

function savePersisted(tabs: WorkbenchTab[], lastActiveProjectId: string | typeof HOME_TAB_ID) {
  try {
    const projectIds = tabs.map((t) => t.projectId);
    const tabMeta: Record<string, { title?: string; path?: string }> = {};
    for (const t of tabs) {
      const meta: { title?: string; path?: string } = {};
      if (t.title && t.title !== "Untitled" && t.title !== "Loading...") {
        meta.title = t.title;
      }
      if (t.path && t.path.length > 0) {
        meta.path = t.path;
      }
      if (Object.keys(meta).length > 0) {
        tabMeta[t.projectId] = meta;
      }
    }
    localStorage.setItem(
      PERSIST_KEY,
      JSON.stringify({ projectIds, lastActiveProjectId, tabMeta } satisfies PersistedTabs)
    );
  } catch {
    // ignore
  }
}

export const WorkbenchTabsProvider = ({ children }: { children: React.ReactNode }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [tabs, setTabs] = React.useState<WorkbenchTab[]>([]);
  const [activeView, setActiveViewState] = React.useState<ActiveView>(HOME_TAB_ID);
  const hasRestoredRef = React.useRef(false);

  // Restore persisted tabs on first mount and navigate to last active (or stay on URL when refreshing on workbench)
  React.useEffect(() => {
    if (hasRestoredRef.current) return;
    hasRestoredRef.current = true;
    const data = loadPersisted();
    const workbenchMatch = location.pathname.match(/^\/workbench\/(.+)$/);
    const urlProjectId = workbenchMatch ? decodeURIComponent(workbenchMatch[1]) : null;

    if (!data) {
      if (urlProjectId) {
        setTabs([{ projectId: urlProjectId, title: "Loading..." }]);
        setActiveViewState(urlProjectId);
      } else {
        navigate("/", { replace: true });
      }
      return;
    }
    const initialTabs: WorkbenchTab[] = data.projectIds.map((id) => ({
      projectId: id,
      title: data.tabMeta?.[id]?.title ?? "Untitled",
      path: data.tabMeta?.[id]?.path,
    }));
    setTabs(initialTabs);
    const last = data.lastActiveProjectId;
    if (last === HOME_TAB_ID) {
      if (urlProjectId) {
        if (!initialTabs.some((t) => t.projectId === urlProjectId)) {
          setTabs([...initialTabs, { projectId: urlProjectId, title: "Loading..." }]);
        }
        setActiveViewState(urlProjectId);
      } else {
        setActiveViewState(HOME_TAB_ID);
        navigate("/", { replace: true });
      }
    } else if (data.projectIds.includes(last)) {
      setActiveViewState(last);
      if (location.pathname !== `/workbench/${encodeURIComponent(last)}`) {
        navigate(`/workbench/${encodeURIComponent(last)}`, { replace: true });
      }
    } else {
      if (urlProjectId && data.projectIds.includes(urlProjectId)) {
        setActiveViewState(urlProjectId);
      } else {
        setActiveViewState(HOME_TAB_ID);
        navigate("/", { replace: true });
      }
    }
  }, [navigate, location.pathname]);

  // Sync activeView from route so it stays correct when navigating (e.g. back/forward or programmatic)
  React.useEffect(() => {
    if (location.pathname === "/") {
      setActiveViewState(HOME_TAB_ID);
      return;
    }
    const match = location.pathname.match(/^\/workbench\/(.+)$/);
    if (match) {
      try {
        const id = decodeURIComponent(match[1]);
        if (id) setActiveViewState(id);
      } catch {
        setActiveViewState(HOME_TAB_ID);
      }
    }
  }, [location.pathname]);

  // Persist whenever tabs or activeView change
  React.useEffect(() => {
    savePersisted(tabs, activeView);
  }, [tabs, activeView]);

  // Ctrl+Tab / Ctrl+Shift+Tab cycle through Home + video tabs
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || (!e.ctrlKey && !e.metaKey)) return;
      const el = e.target as HTMLElement;
      if (el?.closest?.("input, textarea, [contenteditable=\"true\"]")) return;
      e.preventDefault();
      const order: ActiveView[] = [HOME_TAB_ID, ...tabs.map((t) => t.projectId)];
      if (order.length === 0) return;
      const currentIndex =
        activeView === HOME_TAB_ID ? 0 : order.indexOf(activeView);
      const rawIndex = currentIndex === -1 ? 0 : currentIndex;
      const nextIndex = e.shiftKey
        ? (rawIndex - 1 + order.length) % order.length
        : (rawIndex + 1) % order.length;
      const next = order[nextIndex]!;
      setActiveViewState(next);
      if (next === HOME_TAB_ID) {
        navigate("/");
      } else {
        navigate(`/workbench/${encodeURIComponent(next)}`);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [tabs, activeView, navigate]);

  const setActiveView = React.useCallback((view: ActiveView) => {
    setActiveViewState(view);
  }, []);

  const openOrActivateTab = React.useCallback((tab: WorkbenchTab) => {
    setTabs((prev) => upsertTab(prev, tab));
    setActiveViewState(tab.projectId);
  }, []);

  const ensureTab = React.useCallback((tab: WorkbenchTab) => {
    setTabs((prev) => {
      const exists = prev.some((entry) => entry.projectId === tab.projectId);
      if (exists) {
        return prev;
      }
      return [...prev, tab];
    });
  }, []);

  const closeTab = React.useCallback(
    (projectId: string, onSwitchTo?: (next: ActiveView) => void) => {
      const isClosingActive =
        location.pathname.startsWith("/workbench/") &&
        location.pathname === `/workbench/${encodeURIComponent(projectId)}`;

      setTabs((prev) => {
        const nextTabs = prev.filter((t) => t.projectId !== projectId);
        if (isClosingActive && onSwitchTo) {
          const currentIndex = prev.findIndex((t) => t.projectId === projectId);
          if (currentIndex === -1) {
            onSwitchTo(nextTabs.length > 0 ? nextTabs[0].projectId : HOME_TAB_ID);
            return nextTabs;
          }
          if (nextTabs.length === 0) {
            onSwitchTo(HOME_TAB_ID);
          } else {
            const adjacentIndex = currentIndex > 0 ? currentIndex - 1 : 0;
            const nextTab = nextTabs[adjacentIndex] ?? nextTabs[0];
            onSwitchTo(nextTab.projectId);
          }
        }
        return nextTabs;
      });
    },
    [location.pathname]
  );

  const updateTabMeta = React.useCallback(
    (projectId: string, updates: Partial<WorkbenchTab>) => {
      setTabs((prev) => {
        const index = prev.findIndex((tab) => tab.projectId === projectId);
        if (index === -1) {
          return prev;
        }
        const nextTabs = [...prev];
        nextTabs[index] = { ...nextTabs[index], ...updates };
        return nextTabs;
      });
    },
    []
  );

  const reorderTabs = React.useCallback((orderedProjectIds: string[]) => {
    setTabs((prev) => {
      const byId = new Map(prev.map((t) => [t.projectId, t]));
      const next = orderedProjectIds
        .map((id) => byId.get(id))
        .filter((t): t is WorkbenchTab => t != null);
      return next.length > 0 ? next : prev;
    });
  }, []);

  const value = React.useMemo(
    () => ({
      tabs,
      activeView,
      setActiveView,
      openOrActivateTab,
      ensureTab,
      closeTab,
      updateTabMeta,
      reorderTabs,
    }),
    [tabs, activeView, setActiveView, openOrActivateTab, ensureTab, closeTab, updateTabMeta, reorderTabs]
  );

  return (
    <WorkbenchTabsContext.Provider value={value}>{children}</WorkbenchTabsContext.Provider>
  );
};

export const useWorkbenchTabs = () => {
  const context = React.useContext(WorkbenchTabsContext);
  if (!context) {
    throw new Error("useWorkbenchTabs must be used within a WorkbenchTabsProvider.");
  }
  return context;
};
