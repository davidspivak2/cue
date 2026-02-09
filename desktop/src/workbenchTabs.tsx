import * as React from "react";

export type WorkbenchTab = {
  projectId: string;
  title: string;
};

type WorkbenchTabsContextValue = {
  tabs: WorkbenchTab[];
  openOrActivateTab: (tab: WorkbenchTab) => void;
  ensureTab: (tab: WorkbenchTab) => void;
  closeTab: (projectId: string) => void;
  updateTabMeta: (projectId: string, updates: Partial<WorkbenchTab>) => void;
};

const WorkbenchTabsContext = React.createContext<WorkbenchTabsContextValue | null>(null);

const upsertTab = (tabs: WorkbenchTab[], nextTab: WorkbenchTab): WorkbenchTab[] => {
  const index = tabs.findIndex((tab) => tab.projectId === nextTab.projectId);
  if (index === -1) {
    return [...tabs, nextTab];
  }
  const current = tabs[index];
  if (current.title === nextTab.title) {
    return tabs;
  }
  const nextTabs = [...tabs];
  nextTabs[index] = { ...current, ...nextTab };
  return nextTabs;
};

export const WorkbenchTabsProvider = ({ children }: { children: React.ReactNode }) => {
  const [tabs, setTabs] = React.useState<WorkbenchTab[]>([]);

  const openOrActivateTab = React.useCallback((tab: WorkbenchTab) => {
    setTabs((prev) => upsertTab(prev, tab));
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

  const closeTab = React.useCallback((projectId: string) => {
    setTabs((prev) => prev.filter((tab) => tab.projectId !== projectId));
  }, []);

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

  const value = React.useMemo(
    () => ({ tabs, openOrActivateTab, ensureTab, closeTab, updateTabMeta }),
    [tabs, openOrActivateTab, ensureTab, closeTab, updateTabMeta]
  );

  return <WorkbenchTabsContext.Provider value={value}>{children}</WorkbenchTabsContext.Provider>;
};

export const useWorkbenchTabs = () => {
  const context = React.useContext(WorkbenchTabsContext);
  if (!context) {
    throw new Error("useWorkbenchTabs must be used within a WorkbenchTabsProvider.");
  }
  return context;
};
