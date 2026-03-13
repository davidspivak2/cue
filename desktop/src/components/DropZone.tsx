import * as React from "react";

import { Button } from "@/components/ui/button";
import { legacyCopy } from "@/legacyCopy";
import { cn } from "@/lib/utils";

export type DropZoneProps = {
  onFileSelected?: (file: File) => void;
  onChoosePath?: () => void;
  disabled?: boolean;
  className?: string;
  accept?: string;
};

const DropZone = ({
  onFileSelected,
  onChoosePath,
  disabled = false,
  className,
  accept = "video/*"
}: DropZoneProps) => {
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

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(event.target.files);
    event.target.value = "";
  };

  const handleDragEnter = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (disabled) {
      return;
    }
    setIsDragging(true);
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

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-10 text-center transition",
        isDragging ? "border-primary bg-accent/10" : "border-border bg-background/95",
        disabled ? "opacity-60" : "hover:border-primary/60",
        className
      )}
      onDragEnter={handleDragEnter}
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
      <p className="text-lg font-semibold text-foreground">{legacyCopy.dropZone.headline}</p>
      <p className="text-sm text-muted-foreground">{legacyCopy.dropZone.subtext}</p>
      <Button type="button" onClick={openFileDialog} disabled={disabled}>
        {legacyCopy.dropZone.chooseButton}
      </Button>
    </div>
  );
};

export default DropZone;
