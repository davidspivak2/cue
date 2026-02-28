import { Loader2 } from "lucide-react";
import { useAppSplash } from "@/contexts/AppSplashContext";

export default function AppSplash() {
  const { showSplash } = useAppSplash();
  if (!showSplash) return null;

  return (
    <div
      className="fixed inset-0 z-9999 flex flex-col items-center justify-center bg-background"
      data-tauri-drag-region
      aria-live="polite"
      aria-label="Starting Cue"
    >
      <Loader2
        className="h-10 w-10 animate-spin text-muted-foreground"
        aria-hidden
      />
      <p className="mt-4 text-sm text-muted-foreground">Starting Cue...</p>
    </div>
  );
}
