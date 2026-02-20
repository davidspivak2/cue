import * as React from "react";
import { Maximize2, Minus, Settings, Square, X } from "lucide-react";
import { useTheme } from "next-themes";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { isTauri } from "@tauri-apps/api/core";

import { useSettings } from "@/contexts/SettingsContext";
import { cn } from "@/lib/utils";

export const TITLE_BAR_HEIGHT = 36;

export const TITLE_BAR_HEIGHT_PX = `${TITLE_BAR_HEIGHT}px`;

/**
 * Custom window title bar shown only in Tauri (replaces native decorations).
 * Left: Cue logo. Right: Close, Maximize/Restore, Minimize, Settings.
 */
const TitleBar = () => {
  const { openSettings, closeSettings, settingsOpen } = useSettings();
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

  return (
    <header
      data-cue-title-bar
      className={cn(
        "pointer-events-auto fixed left-0 right-0 top-0 z-[100] flex h-[var(--title-bar-height)] select-none items-center justify-between",
        "border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80"
      )}
      style={{ "--title-bar-height": TITLE_BAR_HEIGHT_PX } as React.CSSProperties}
    >
      {/* Full-size drag layer so the entire top strip is draggable (fixes drag at top when maximized) */}
      <div
        className="absolute inset-0 cursor-default"
        data-tauri-drag-region
        onDoubleClick={handleMaximize}
        aria-hidden
      />

      {/* Logo + app name: visual only, clicks pass through to drag layer */}
      <div className="relative z-10 flex flex-1 pointer-events-none items-center gap-2 pl-3">
        <img
          src={resolvedTheme === "dark" ? "/dark.svg" : "/light.svg"}
          alt=""
          className="h-5 w-5 shrink-0"
          aria-hidden
        />
        <span className="text-lg font-medium tracking-tight text-foreground">Cue</span>
      </div>

      {/* Window controls: order left-to-right = Settings, Minimize, Maximize, Close */}
      <div className="relative z-10 flex self-stretch items-stretch">
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
