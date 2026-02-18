import * as React from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { legacyCopy } from "@/legacyCopy";
import { cn } from "@/lib/utils";

export type VideoCardProps = {
  fileName?: string;
  durationLabel?: string;
  thumbnailUrl?: string;
  previewKind?: "image" | "video";
  onClear?: () => void;
  onFileSelected?: (file: File) => void;
  onChoosePath?: () => void;
  disabled?: boolean;
  className?: string;
  accept?: string;
};

const VideoCard = ({
  fileName,
  durationLabel,
  thumbnailUrl,
  previewKind = "image",
  onClear,
  onFileSelected,
  onChoosePath,
  disabled = false,
  className,
  accept = "video/*"
}: VideoCardProps) => {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = React.useState(false);

  const handleFiles = React.useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) {
        return;
      }
      onFileSelected?.(files[0]);
    },
    [onFileSelected]
  );

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(event.target.files);
    event.target.value = "";
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (disabled) {
      return;
    }
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    if (disabled) {
      return;
    }
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (disabled) {
      return;
    }
    setIsDragging(false);
    handleFiles(event.dataTransfer.files);
  };

  const openFileDialog = () => {
    if (disabled) {
      return;
    }
    if (onChoosePath) {
      onChoosePath();
      return;
    }
    inputRef.current?.click();
  };

  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-3 transition",
        isDragging ? "border-primary ring-2 ring-primary/20" : "border-border",
        disabled ? "opacity-60" : "hover:border-primary/60",
        className
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      aria-disabled={disabled}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleInputChange}
        disabled={disabled}
      />
      <div
        className={cn(
          "relative w-full overflow-hidden rounded-lg border border-border bg-muted",
          (onFileSelected || onChoosePath) && "cursor-pointer"
        )}
        style={{ aspectRatio: "16 / 9" }}
        onClick={onFileSelected || onChoosePath ? openFileDialog : undefined}
      >
        {thumbnailUrl ? (
          previewKind === "video" ? (
            <video
              src={thumbnailUrl}
              className="h-full w-full object-cover"
              preload="metadata"
              muted
              playsInline
            />
          ) : (
            <img
              src={thumbnailUrl}
              alt={fileName || ""}
              className="h-full w-full object-cover"
            />
          )
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
            {legacyCopy.videoCard.placeholder}
          </div>
        )}
        {onClear && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute right-2 top-2 h-8 w-8 rounded-full border border-border bg-background/90 text-foreground shadow-sm transition-colors duration-200 hover:bg-background"
            onClick={onClear}
            aria-label={legacyCopy.videoCard.remove}
            disabled={disabled}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
      {(fileName || durationLabel) && (
        <div className="mt-3 space-y-1">
          {fileName && <p className="text-sm font-medium text-foreground">{fileName}</p>}
          {durationLabel && <p className="text-xs text-muted-foreground">{durationLabel}</p>}
        </div>
      )}
    </div>
  );
};

export default VideoCard;
