import * as React from "react";
import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  horizontalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Home, Maximize2, Minus, Settings, Square, Video, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "next-themes";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";

import { useSettings } from "@/contexts/SettingsContext";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useWindowWidth } from "@/hooks/useWindowWidth";
import { normalizeLocalPath } from "@/lib/normalizeLocalPath";
import { truncatePathMiddle } from "@/lib/truncatePathMiddle";
import { cn } from "@/lib/utils";
import { HOME_TAB_ID, useWorkbenchTabs } from "@/workbenchTabs";
import type { ActiveView, WorkbenchTab } from "@/workbenchTabs";

/** Breakpoints for title bar tab layout (window width). */
const TITLE_BAR_WIDE = 720;
const TITLE_BAR_MEDIUM = 520;
type TabLayoutMode = "wide" | "medium" | "narrow";

function getTabLayoutMode(width: number): TabLayoutMode {
  if (width >= TITLE_BAR_WIDE) return "wide";
  if (width >= TITLE_BAR_MEDIUM) return "medium";
  return "narrow";
}

export const TITLE_BAR_HEIGHT = 36;

export const TITLE_BAR_HEIGHT_PX = `${TITLE_BAR_HEIGHT}px`;

function SortableTitleTab({
  tab,
  isActive,
  layoutMode,
  onTabClick,
  onCloseTab,
}: {
  tab: WorkbenchTab;
  isActive: boolean;
  layoutMode: TabLayoutMode;
  onTabClick: (projectId: string) => void;
  onCloseTab: (projectId: string, e: React.MouseEvent) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: tab.projectId });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const isIconOnly = layoutMode === "narrow";
  const maxWidthClass =
    layoutMode === "wide"
      ? "max-w-[180px]"
      : layoutMode === "medium"
        ? "max-w-[100px]"
        : "max-w-[44px]";

  const thumbnailSrc =
    isIconOnly && tab.thumbnail_path
      ? convertFileSrc(normalizeLocalPath(tab.thumbnail_path))
      : null;
  const title = tab.title || "Untitled";
  const tooltipText =
    tab.path && tab.path.length > 0 ? truncatePathMiddle(tab.path, 56) : title;

  const [tabHover, setTabHover] = React.useState(false);

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-testid={`title-bar-tab-${tab.projectId}`}
      className={cn(
        "flex h-full shrink-0 items-center gap-1 border-b-2 border-r border-foreground/15 pl-3 pr-2 transition-colors duration-200",
        maxWidthClass,
        isActive
          ? "border-b-foreground/30 bg-foreground/8"
          : "border-b-transparent hover:bg-foreground/5",
        isDragging && "opacity-60 shadow-md z-50"
      )}
      {...attributes}
      {...listeners}
      onPointerEnter={() => setTabHover(true)}
      onPointerLeave={() => setTabHover(false)}
    >
      <TooltipProvider delayDuration={300}>
        <Tooltip open={tabHover}>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={(e) => {
                if (isActive) {
                  e.preventDefault();
                  e.stopPropagation();
                  return;
                }
                onTabClick(tab.projectId);
              }}
              className={cn(
                "flex min-w-0 flex-1 items-center gap-1 truncate py-1.5 text-left text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                isIconOnly && "flex-1 justify-center p-1",
                isActive && "!cursor-default"
              )}
            >
              {isIconOnly ? (
                thumbnailSrc ? (
                  <img
                    src={thumbnailSrc}
                    alt=""
                    className="h-5 w-5 shrink-0 object-cover"
                    aria-hidden
                  />
                ) : (
                  <Video className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                )
              ) : (
                title
              )}
            </button>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={6}>
            {tooltipText}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <button
        type="button"
        onClick={(e) => onCloseTab(tab.projectId, e)}
        aria-label={`Close ${title}`}
        data-testid={`title-bar-tab-close-${tab.projectId}`}
        className="shrink-0 rounded-md p-0.5 hover:bg-foreground/15 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <X className="h-3.5 w-3.5 text-muted-foreground" />
      </button>
    </div>
  );
}

function HomeTabWithTooltip({
  activeView,
  onHomeClick,
}: {
  activeView: ActiveView;
  onHomeClick: () => void;
}) {
  const [homeHover, setHomeHover] = React.useState(false);
  return (
    <div
      className="h-full"
      onPointerEnter={() => setHomeHover(true)}
      onPointerLeave={() => setHomeHover(false)}
    >
      <TooltipProvider delayDuration={300}>
        <Tooltip open={homeHover}>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={(e) => {
                if (activeView === HOME_TAB_ID) {
                  e.preventDefault();
                  e.stopPropagation();
                  return;
                }
                onHomeClick();
              }}
              aria-label="Home"
              data-testid="title-bar-home"
              aria-current={activeView === HOME_TAB_ID ? "true" : undefined}
              className={cn(
                "flex h-full w-10 shrink-0 items-center justify-center self-stretch border-b-2 border-r border-foreground/15 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                activeView === HOME_TAB_ID
                  ? "!cursor-default border-b-foreground/30 bg-foreground/8 text-foreground"
                  : "border-b-transparent text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
              )}
            >
              <Home className="h-4 w-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={6}>
            Home
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}

/**
 * Custom window title bar shown only in Tauri (replaces native decorations).
 * Left: Cue logo (draggable). Middle: tab strip (Home icon + video tabs). Right: Settings, Minimize, Maximize, Close.
 * Only the logo area has data-tauri-drag-region so the tab strip stays clickable and future drag-to-reorder works.
 */
const TitleBar = () => {
  const navigate = useNavigate();
  const width = useWindowWidth();
  const tabLayoutMode = getTabLayoutMode(width);
  const { openSettings, closeSettings, settingsOpen } = useSettings();
  const { tabs, activeView, setActiveView, closeTab, reorderTabs } = useWorkbenchTabs();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const handleDragEnd = React.useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;
      const order = tabs.map((t) => t.projectId);
      const oldIndex = order.indexOf(active.id as string);
      const newIndex = order.indexOf(over.id as string);
      if (oldIndex === -1 || newIndex === -1) return;
      reorderTabs(arrayMove(order, oldIndex, newIndex));
    },
    [tabs, reorderTabs]
  );
  const { resolvedTheme } = useTheme();
  const [maximized, setMaximized] = React.useState(false);
  const appWindow = React.useMemo(
    () => (typeof window !== "undefined" && isTauri() ? getCurrentWindow() : null),
    []
  );

  React.useEffect(() => {
    if (!appWindow) return;
    const check = async () => {
      try {
        setMaximized(await appWindow.isMaximized());
      } catch {
        // ignore
      }
    };
    void check();
    const unlistenPromise = appWindow.onFocusChanged(() => void check());
    return () => {
      unlistenPromise.then((u) => u()).catch(() => {});
    };
  }, [appWindow]);

  const handleMinimize = React.useCallback(() => {
    appWindow?.minimize();
  }, [appWindow]);

  const handleMaximize = React.useCallback(async () => {
    await appWindow?.toggleMaximize();
    try {
      if (appWindow) setMaximized(await appWindow.isMaximized());
    } catch {
      setMaximized((prev) => !prev);
    }
  }, [appWindow]);

  const handleClose = React.useCallback(() => {
    appWindow?.close();
  }, [appWindow]);

  if (!isTauri()) {
    return null;
  }

  const handleHomeClick = () => {
    setActiveView(HOME_TAB_ID);
    navigate("/");
  };

  const handleTabClick = (projectId: string) => {
    if (activeView === projectId) return;
    setActiveView(projectId);
    navigate(`/workbench/${encodeURIComponent(projectId)}`);
  };

  const handleCloseTab = (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    closeTab(projectId, (next) => {
      if (next === HOME_TAB_ID) navigate("/");
      else navigate(`/workbench/${encodeURIComponent(next)}`);
    });
  };

  return (
    <header
      data-cue-title-bar
      data-testid="title-bar"
      className={cn(
        "pointer-events-auto fixed left-0 right-0 top-0 z-[100] flex h-[var(--title-bar-height)] select-none items-stretch",
        "border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80"
      )}
      style={{ "--title-bar-height": TITLE_BAR_HEIGHT_PX } as React.CSSProperties}
    >
      {/* Left: logo + Cue — only this area is draggable so tab strip stays clickable */}
      <div
        className="relative z-10 flex shrink-0 cursor-default items-center gap-2 pl-3 pr-2"
        data-tauri-drag-region
        onDoubleClick={handleMaximize}
      >
        <img
          src={resolvedTheme === "dark" ? "/dark.svg" : "/light.svg"}
          alt=""
          className="h-5 w-5 shrink-0 pointer-events-none"
          aria-hidden
        />
        <span className="pointer-events-none text-lg font-medium tracking-tight text-foreground">
          Cue
        </span>
      </div>

      {/* Tab strip: Home + video tabs (sortable). Drag region on container so empty space (between tabs and window controls) drags window; clicks on Home/tabs still hit those elements. */}
      <div
        className="relative z-10 flex h-full min-w-0 flex-1 items-stretch gap-0 overflow-hidden"
        data-tauri-drag-region
        onDoubleClick={handleMaximize}
      >
        <HomeTabWithTooltip
          activeView={activeView}
          onHomeClick={handleHomeClick}
        />
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          <SortableContext
            items={tabs.map((t) => t.projectId)}
            strategy={horizontalListSortingStrategy}
          >
            {tabs.map((tab) => (
              <SortableTitleTab
                key={tab.projectId}
                tab={tab}
                isActive={activeView === tab.projectId}
                layoutMode={tabLayoutMode}
                onTabClick={handleTabClick}
                onCloseTab={handleCloseTab}
              />
            ))}
          </SortableContext>
        </DndContext>
      </div>

      {/* Window controls: order left-to-right = Settings, Minimize, Maximize, Close */}
      <div className="relative z-10 flex shrink-0 self-stretch items-stretch">
        <TitleBarButton
          onClick={settingsOpen ? closeSettings : openSettings}
          title="Settings"
          aria-label="Settings"
          selected={settingsOpen}
        >
          <Settings className="h-4 w-4" />
        </TitleBarButton>
        <TitleBarButton
          onClick={handleMinimize}
          title="Minimize"
          aria-label="Minimize"
          windowControl
        >
          <Minus className="h-4 w-4" />
        </TitleBarButton>
        <TitleBarButton
          onClick={handleMaximize}
          title={maximized ? "Restore" : "Maximize"}
          aria-label={maximized ? "Restore" : "Maximize"}
          windowControl
        >
          {maximized ? (
            <Maximize2 className="h-4 w-4" />
          ) : (
            <Square className="h-3.5 w-4" strokeWidth={2} />
          )}
        </TitleBarButton>
        <TitleBarButton
          onClick={handleClose}
          title="Close"
          className="hover:bg-destructive hover:text-destructive-foreground"
          aria-label="Close"
          windowControl
        >
          <X className="h-4 w-4" />
        </TitleBarButton>
      </div>
    </header>
  );
};

function TitleBarButton({
  children,
  onClick,
  title,
  className,
  "aria-label": ariaLabel,
  selected = false,
  windowControl = false,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  title: string;
  className?: string;
  "aria-label": string;
  selected?: boolean;
  windowControl?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={ariaLabel}
      aria-pressed={selected}
      data-cue-title-bar-window-control={windowControl ? "true" : undefined}
      className={cn(
        "flex h-full w-10 items-center justify-center text-foreground transition-colors duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        selected ? "bg-foreground/10" : "hover:bg-foreground/10 active:bg-foreground/15",
        className
      )}
    >
      {children}
    </button>
  );
}

export default TitleBar;
