import * as React from "react";
import { Suspense, lazy } from "react";
import { useWorkbenchTabs, HOME_TAB_ID } from "@/workbenchTabs";
import { RouteErrorBoundary } from "@/components/RouteErrorBoundary";
import { WorkbenchSkeleton } from "@/components/WorkbenchSkeleton";
import ProjectHub from "@/pages/ProjectHub";

const Workbench = lazy(() => import("@/pages/Workbench"));

/**
 * Renders Home + all open workbench tabs. Only the active tab's content is visible;
 * others stay mounted but hidden so switching back is instant (no reload).
 */
const TabHost = () => {
  const { tabs, activeView } = useWorkbenchTabs();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        className="flex min-h-0 flex-1 flex-col"
        style={{ display: activeView === HOME_TAB_ID ? "flex" : "none" }}
        aria-hidden={activeView !== HOME_TAB_ID}
      >
        <ProjectHub />
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.projectId}
          className="flex min-h-0 flex-1 flex-col"
          style={{ display: activeView === tab.projectId ? "flex" : "none" }}
          aria-hidden={activeView !== tab.projectId}
        >
          <Suspense fallback={<WorkbenchSkeleton />}>
            <RouteErrorBoundary>
              <Workbench projectId={tab.projectId} />
            </RouteErrorBoundary>
          </Suspense>
        </div>
      ))}
    </div>
  );
};

export default TabHost;
