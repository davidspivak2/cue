import * as React from "react";
import { ChevronLeft, ChevronRight, Home, Settings } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { WorkbenchTabsProvider } from "@/workbenchTabs";

const SIDEBAR_STORAGE_KEY = "cue_sidebar_collapsed_v1";

const navItems = [
  { label: "Projects", to: "/", icon: Home },
  { label: "Settings", to: "/settings", icon: Settings }
];

const AppLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const hasLaunchedRef = React.useRef(false);
  const [isCollapsed, setIsCollapsed] = React.useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
  });

  React.useEffect(() => {
    if (hasLaunchedRef.current) {
      return;
    }
    hasLaunchedRef.current = true;
    if (location.pathname !== "/") {
      navigate("/", { replace: true });
    }
  }, [location.pathname, navigate]);

  React.useEffect(() => {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(isCollapsed));
  }, [isCollapsed]);

  return (
    <WorkbenchTabsProvider>
      <div className="min-h-screen bg-background text-foreground">
        <div className="flex min-h-screen">
          <aside
            className={cn(
              "border-r border-border bg-card",
              isCollapsed ? "w-16" : "w-60"
            )}
          >
            <div
              className={cn(
                "flex h-16 items-center text-lg font-semibold",
                isCollapsed ? "justify-center px-2" : "justify-between px-4"
              )}
            >
              <span>{isCollapsed ? "C" : "Cue"}</span>
              {!isCollapsed && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsCollapsed(true)}
                  aria-label="Collapse sidebar"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              )}
            </div>
            {isCollapsed && (
              <div className="flex justify-center pb-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsCollapsed(false)}
                  aria-label="Expand sidebar"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
            <nav className={cn("space-y-1 pb-4", isCollapsed ? "px-1" : "px-2")}>
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.label}
                    to={item.to}
                    title={item.label}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center rounded-md text-sm transition-colors",
                        isCollapsed ? "justify-center px-2 py-2" : "gap-2 px-3 py-2",
                        isActive
                          ? "bg-secondary text-foreground"
                          : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground"
                      )
                    }
                  >
                    <Icon className="h-4 w-4" />
                    <span className={cn(isCollapsed ? "sr-only" : "")}>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>
          </aside>
          <main className="flex-1 px-6 py-6">
            <Outlet />
          </main>
        </div>
      </div>
    </WorkbenchTabsProvider>
  );
};

export default AppLayout;
