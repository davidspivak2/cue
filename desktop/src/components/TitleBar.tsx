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

/** Width reserved for logo + Cue label (px). */
const TITLE_BAR_LOGO_WIDTH = 90;
/** Width for Home tab (w-10). */
const TITLE_BAR_HOME_WIDTH = 40;
/** Width for window controls (4 × w-10). */
const TITLE_BAR_CONTROLS_WIDTH = 160;
/** Min width per tab in "wide" mode (max-w-[180px] + padding/close). */
const TITLE_BAR_WIDE_TAB_PX = 180;
/** Window width below which we use "narrow" when we can't fit wide tabs. */
const TITLE_BAR_NARROW_BREAKPOINT = 520;
type TabLayoutMode = "wide" | "medium" | "narrow";

function getTabLayoutMode(
  windowWidth: number,
  tabCount: number
): TabLayoutMode {
  const availableForTabs =
    windowWidth - TITLE_BAR_LOGO_WIDTH - TITLE_BAR_HOME_WIDTH - TITLE_BAR_CONTROLS_WIDTH;
  const requiredForWide = tabCount * TITLE_BAR_WIDE_TAB_PX;
  if (availableForTabs >= requiredForWide) return "wide";
  if (windowWidth >= TITLE_BAR_NARROW_BREAKPOINT) return "medium";
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
  const hoverTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const TOOLTIP_DELAY_MS = 400;

  const clearHoverTimeout = () => {
    if (hoverTimeoutRef.current !== null) {
      clearTimeout(hoverTimeoutRef.current);
      hoverTimeoutRef.current = null;
    }
  };

  const handlePointerEnter = () => {
    clearHoverTimeout();
    hoverTimeoutRef.current = setTimeout(() => setTabHover(true), TOOLTIP_DELAY_MS);
  };

  const handlePointerLeave = () => {
    clearHoverTimeout();
    setTabHover(false);
  };

  React.useEffect(() => () => clearHoverTimeout(), []);

  const handleAuxClick = (e: React.MouseEvent) => {
    if (e.button === 1) {
      e.preventDefault();
      e.stopPropagation();
      onCloseTab(tab.projectId, e);
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-testid={`title-bar-tab-${tab.projectId}`}
      onAuxClick={handleAuxClick}
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
    >
      <div
        className="min-w-0 flex-1"
        onPointerEnter={handlePointerEnter}
        onPointerLeave={handlePointerLeave}
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
                <span className="block min-w-0 truncate">{title}</span>
              )}
            </button>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={6}>
            {tooltipText}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      </div>
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

function HomeTab({
  activeView,
  onHomeClick,
  hasOtherTabs,
}: {
  activeView: ActiveView;
  onHomeClick: () => void;
  hasOtherTabs: boolean;
}) {
  return (
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
        "flex h-full w-10 shrink-0 items-center justify-center self-stretch border-b-2 transition-colors duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        hasOtherTabs && "border-r border-foreground/15",
        hasOtherTabs && activeView === HOME_TAB_ID && "border-l border-foreground/15",
        activeView === HOME_TAB_ID
          ? "!cursor-default border-b-foreground/30 bg-foreground/8 text-foreground"
          : "border-b-transparent text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
      )}
    >
      <Home className="h-4 w-4" />
    </button>
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
  const { openSettings, closeSettings, settingsOpen } = useSettings();
  const [settingsSpinKey, setSettingsSpinKey] = React.useState(0);
  const [settingsSpinDirection, setSettingsSpinDirection] = React.useState<
    "open" | "close" | null
  >(null);
  const prevSettingsOpenRef = React.useRef(settingsOpen);
  const { tabs, activeView, setActiveView, closeTab, reorderTabs } = useWorkbenchTabs();
  const tabLayoutMode = getTabLayoutMode(width, tabs.length);

  React.useEffect(() => {
    if (prevSettingsOpenRef.current && !settingsOpen) {
      setSettingsSpinDirection("close");
      setSettingsSpinKey((k) => k + 1);
    }
    prevSettingsOpenRef.current = settingsOpen;
  }, [settingsOpen]);

  const handleSettingsClick = React.useCallback(() => {
    if (settingsOpen) {
      closeSettings();
    } else {
      setSettingsSpinDirection("open");
      setSettingsSpinKey((k) => k + 1);
      openSettings();
    }
  }, [settingsOpen, openSettings, closeSettings]);

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
        <span className="pointer-events-none text-base font-semibold tracking-tight text-foreground">
          Cue
        </span>
      </div>

      {/* Tab strip: Home + video tabs (sortable). Drag region on container so empty space (between tabs and window controls) drags window; clicks on Home/tabs still hit those elements. */}
      <div
        className="relative z-10 flex h-full min-w-0 flex-1 items-stretch gap-0 overflow-hidden"
        data-tauri-drag-region
        onDoubleClick={handleMaximize}
      >
        <HomeTab
          activeView={activeView}
          onHomeClick={handleHomeClick}
          hasOtherTabs={tabs.length > 0}
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
          onClick={handleSettingsClick}
          title="Settings"
          aria-label="Settings"
          selected={settingsOpen}
        >
          <span
            key={settingsSpinKey}
            className={cn(
              "inline-block",
              settingsSpinKey > 0 &&
                (settingsSpinDirection === "open"
                  ? "animate-settings-icon-spin"
                  : "animate-settings-icon-spin-reverse")
            )}
          >
            <Settings className="h-4 w-4" />
          </span>
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
