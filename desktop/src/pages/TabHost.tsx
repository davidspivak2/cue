import { Suspense, lazy, useEffect, useRef } from "react";
import { useWorkbenchTabs, HOME_TAB_ID } from "@/workbenchTabs";
import { RouteErrorBoundary } from "@/components/RouteErrorBoundary";
import { WorkbenchSkeleton } from "@/components/WorkbenchSkeleton";
import ProjectHub from "@/pages/ProjectHub";

const Workbench = lazy(() => import("@/pages/Workbench"));

/**
 * Renders Home + all open workbench tabs. Only the active tab's content is visible;
 * others stay mounted but hidden so switching back is instant (no reload).
 * Uses inert on hidden panels so focus is not retained in hidden content (avoids
 * "Blocked aria-hidden" a11y violation when a focused descendant is hidden).
 */
const TabHost = () => {
  const { tabs, activeView } = useWorkbenchTabs();
  const homePanelRef = useRef<HTMLDivElement>(null);
  const activePanelRef = useRef<HTMLDivElement | null>(null);
  const panelRefsRef = useRef<Map<string, HTMLDivElement>>(new Map());

  useEffect(() => {
    const el = activePanelRef.current;
    if (el) {
      el.focus({ preventScroll: true });
    }
  }, [activeView]);

  useEffect(() => {
    const isHomeActive = activeView === HOME_TAB_ID;
    if (homePanelRef.current) {
      homePanelRef.current.inert = !isHomeActive;
    }
    panelRefsRef.current.forEach((panel, projectId) => {
      panel.inert = activeView !== projectId;
    });
  }, [activeView, tabs.length]);

  const isHomeActive = activeView === HOME_TAB_ID;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={(el) => {
          homePanelRef.current = el;
          if (isHomeActive) activePanelRef.current = el;
        }}
        className="flex min-h-0 flex-1 flex-col outline-none"
        style={{ display: isHomeActive ? "flex" : "none" }}
        tabIndex={-1}
      >
        <ProjectHub />
      </div>
      {tabs.map((tab) => {
        const isActive = activeView === tab.projectId;
        return (
          <div
            key={tab.projectId}
            ref={(el) => {
              if (el) {
                panelRefsRef.current.set(tab.projectId, el);
                if (isActive) activePanelRef.current = el;
              } else {
                panelRefsRef.current.delete(tab.projectId);
              }
            }}
            className="flex min-h-0 flex-1 flex-col outline-none"
            style={{ display: isActive ? "flex" : "none" }}
            tabIndex={-1}
          >
            <Suspense fallback={<WorkbenchSkeleton />}>
              <RouteErrorBoundary>
                <Workbench projectId={tab.projectId} />
              </RouteErrorBoundary>
            </Suspense>
          </div>
        );
      })}
    </div>
  );
};

export default TabHost;
