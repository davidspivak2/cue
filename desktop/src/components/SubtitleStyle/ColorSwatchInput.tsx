import * as React from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

type ColorSwatchInputProps = {
  value: string;
  onChange: (color: string) => void;
  swatches?: string[];
  className?: string;
};

const ColorSwatchInput = ({
  value,
  onChange,
  swatches = [],
  className
}: ColorSwatchInputProps) => {
  const [draft, setDraft] = React.useState(value);

  React.useEffect(() => {
    setDraft(value);
  }, [value]);

  const commitDraft = () => {
    const normalized = draft.startsWith("#") ? draft : `#${draft}`;
    if (HEX_RE.test(normalized)) {
      onChange(normalized);
    } else {
      setDraft(value);
    }
  };

  return (
    <div className={cn("flex min-w-0 items-center gap-2", className)}>
      {swatches.map((swatch) => (
        <button
          key={swatch}
          type="button"
          aria-label={`Select color ${swatch}`}
          className={cn(
            "h-6 w-6 shrink-0 rounded-full border-2 transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            value.toLowerCase() === swatch.toLowerCase()
              ? "border-foreground"
              : "border-transparent"
          )}
          style={{ backgroundColor: swatch }}
          onClick={() => onChange(swatch)}
        />
      ))}
      <Input
        className="h-7 w-20 px-2 font-mono text-xs"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commitDraft}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            commitDraft();
          }
        }}
      />
      <div
        className="h-6 w-6 shrink-0 rounded border border-border"
        style={{ backgroundColor: value }}
        aria-hidden
      />
    </div>
  );
};

export default ColorSwatchInput;
