import * as React from "react";

import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { OpacitySlider } from "@/components/ui/opacity-slider";
import { HueSlider } from "@/components/ui/hue-slider";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { hexToHsv, hsvToHex, pickContrastingColor, SWATCH_SETS, type ColorKind } from "./colorUtils";

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

type ColorPopoverContentProps = {
  value: string;
  onChange: (hex: string) => void;
  opacity: number;
  onOpacityChange: (opacity: number) => void;
  presets: readonly string[];
};

export function ColorPopoverContent({
  value,
  onChange,
  opacity,
  onOpacityChange,
  presets
}: ColorPopoverContentProps) {
  const validHex = HEX_RE.test(value) ? value : "#ffffff";
  const [hsv, setHsv] = React.useState(() => hexToHsv(validHex) ?? { h: 0, s: 1, v: 1 });
  const [hexInput, setHexInput] = React.useState(validHex);
  const boxRef = React.useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = React.useState(false);
  const selectedHex = hsvToHex(hsv.h, hsv.s, hsv.v);
  const selectorRingColor = pickContrastingColor(selectedHex);

  React.useEffect(() => {
    if (HEX_RE.test(value)) {
      const next = hexToHsv(value);
      if (next) {
        setHsv(next);
        setHexInput(value);
      }
    }
  }, [value]);

  const syncFromHsv = React.useCallback((h: number, s: number, v: number) => {
    const hex = hsvToHex(h, s, v);
    setHexInput(hex);
    onChange(hex);
  }, [onChange]);

  const handleBoxMove = React.useCallback(
    (clientX: number, clientY: number) => {
      const el = boxRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
      const s = x;
      const v = 1 - y;
      setHsv((prev) => {
        const next = { ...prev, s, v };
        queueMicrotask(() => syncFromHsv(next.h, next.s, next.v));
        return next;
      });
    },
    [syncFromHsv]
  );

  const handleBoxMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setDragging(true);
    handleBoxMove(e.clientX, e.clientY);
  };

  React.useEffect(() => {
    if (!dragging) return;
    const onMove = (e: MouseEvent) => handleBoxMove(e.clientX, e.clientY);
    const onUp = () => setDragging(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging, handleBoxMove]);

  const handleHueChange = (h: number) => {
    setHsv((prev) => {
      const next = { ...prev, h };
      queueMicrotask(() => syncFromHsv(next.h, next.s, next.v));
      return next;
    });
  };

  const commitHex = () => {
    const raw = hexInput.startsWith("#") ? hexInput : `#${hexInput}`;
    if (HEX_RE.test(raw)) {
      onChange(raw);
      const next = hexToHsv(raw);
      if (next) setHsv(next);
    }
  };

  return (
    <div className="space-y-3">
      <div
        ref={boxRef}
        className="relative h-32 w-full cursor-crosshair overflow-visible rounded-[5px] border border-border"
        onMouseDown={handleBoxMouseDown}
        role="slider"
        aria-label="Saturation and value"
        tabIndex={0}
        onKeyDown={(e) => {
          const step = e.shiftKey ? 10 : 1;
          if (e.key === "ArrowLeft") {
            e.preventDefault();
            handleBoxMove(0, 0);
            setHsv((prev) => {
              const s = Math.max(0, prev.s - step / 100);
              const next = { ...prev, s };
              queueMicrotask(() => syncFromHsv(next.h, next.s, next.v));
              return next;
            });
          }
          if (e.key === "ArrowRight") {
            e.preventDefault();
            setHsv((prev) => {
              const s = Math.min(1, prev.s + step / 100);
              const next = { ...prev, s };
              queueMicrotask(() => syncFromHsv(next.h, next.s, next.v));
              return next;
            });
          }
        }}
      >
        <div
          className="pointer-events-none absolute inset-0 overflow-hidden rounded-[4px]"
          style={{
            background: `
              linear-gradient(to bottom, transparent 0%, black 100%),
              linear-gradient(to right, white 0%, hsl(${hsv.h}, 100%, 50%) 100%)
            `
          }}
        />
        <div
          className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 shadow-[0_1px_4px_rgba(15,23,42,0.55)]"
          style={{
            left: `${hsv.s * 100}%`,
            top: `${(1 - hsv.v) * 100}%`,
            borderColor: selectorRingColor,
            backgroundColor: selectedHex
          }}
        />
      </div>

      <div>
        <Label className="text-sm text-foreground">Hue</Label>
        <HueSlider
          className="mt-1.5"
          min={0}
          max={360}
          step={1}
          value={[hsv.h]}
          onValueChange={([h = 0]) => handleHueChange(h)}
          aria-label="Hue"
        />
      </div>

      <div className="space-y-1">
        <Label className="text-sm text-foreground">Opacity</Label>
        <div className="grid grid-cols-[1fr_auto] items-center gap-3">
          <OpacitySlider
            min={0}
            max={100}
            step={1}
            opaqueColor={validHex}
            value={[Math.round(opacity * 100)]}
            onValueChange={([v]) => onOpacityChange(v / 100)}
          />
          <div className="flex h-8 items-stretch overflow-hidden rounded-md border border-input bg-background">
            <Button
              type="button"
              variant="ghost"
              size="iconSm"
              className="h-full w-7 rounded-none"
              aria-label="Decrease opacity"
              onClick={() => {
                const next = Math.max(0, Math.round(opacity * 100) - 1);
                onOpacityChange(next / 100);
              }}
              disabled={Math.round(opacity * 100) <= 0}
            >
              <span className="text-xs leading-none">-</span>
            </Button>
            <Input
              type="number"
              className="h-full w-12 rounded-none border-0 bg-transparent px-2 text-center text-xs focus-visible:ring-0"
              min={0}
              max={100}
              step={1}
              value={Math.round(opacity * 100)}
              aria-label="Opacity"
              onChange={(event) => {
                const nextValue = Number(event.target.value);
                if (!Number.isNaN(nextValue)) {
                  const clamped = Math.max(0, Math.min(100, nextValue));
                  onOpacityChange(clamped / 100);
                }
              }}
            />
            <Button
              type="button"
              variant="ghost"
              size="iconSm"
              className="h-full w-7 rounded-none"
              aria-label="Increase opacity"
              onClick={() => {
                const next = Math.min(100, Math.round(opacity * 100) + 1);
                onOpacityChange(next / 100);
              }}
              disabled={Math.round(opacity * 100) >= 100}
            >
              <span className="text-xs leading-none">+</span>
            </Button>
          </div>
        </div>
      </div>

      <div>
        <Label className="text-sm text-foreground">Hex</Label>
        <div className="mt-1.5 flex items-center gap-2">
          <Input
            className="h-8 w-24 font-mono text-xs bg-background text-foreground border border-input"
            value={hexInput}
            onChange={(e) => setHexInput(e.target.value)}
            onPaste={(e) => {
              const text = e.clipboardData.getData("text");
              if (!text) {
                return;
              }
              e.preventDefault();
              const cleaned = text.trim();
              const next = cleaned.startsWith("#") ? cleaned : `#${cleaned}`;
              setHexInput(next);
            }}
            onBlur={commitHex}
            onKeyDown={(e) => e.key === "Enter" && commitHex()}
            placeholder="#FFFFFF"
          />
          <div
            className="h-8 aspect-square shrink-0 rounded border border-border"
            style={{ backgroundColor: HEX_RE.test(hexInput) ? hexInput : "#fff" }}
            aria-hidden
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label className="text-sm text-foreground">Presets</Label>
        <div className="flex flex-wrap gap-1.5">
          {presets.map((swatch) => (
            <button
              key={swatch}
              type="button"
              aria-label={`Select ${swatch}`}
              className={cn(
                "h-6 w-6 shrink-0 rounded-full border border-black/70 transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                value.toLowerCase() === swatch.toLowerCase() &&
                  "border-foreground ring-2 ring-foreground/30"
              )}
              style={{ backgroundColor: swatch }}
              onClick={() => {
                onChange(swatch);
                const next = hexToHsv(swatch);
                if (next) setHsv(next);
                setHexInput(swatch);
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export type ColorRowProps = {
  value: string;
  onChange: (color: string) => void;
  kind: ColorKind;
  opacity?: number;
  onOpacityChange?: (opacity: number) => void;
  outlineAuto?: boolean;
  onOutlineAutoChange?: (auto: boolean) => void;
  /** When true, do not render the Auto button (e.g. when Auto is a separate control). */
  hideAutoButton?: boolean;
  /** When true, show only a single swatch that opens the popover; presets are inside the popover only. */
  compact?: boolean;
  className?: string;
};

export function ColorRow({
  value,
  onChange,
  kind,
  opacity = 1,
  onOpacityChange,
  outlineAuto = false,
  onOutlineAutoChange,
  hideAutoButton = false,
  compact = false,
  className
}: ColorRowProps) {
  const set = SWATCH_SETS[kind];
  const presets = "full" in set ? set.full : [];
  const outlineWithAuto = "hasAuto" in set && set.hasAuto;
  const panePresets = outlineWithAuto
    ? presets.slice(0, set.paneCount - 1)
    : presets.slice(0, set.paneCount);
  const [open, setOpen] = React.useState(false);

  const isPresetSelected = outlineWithAuto
    ? value !== "auto" && panePresets.some((p) => p.toLowerCase() === value.toLowerCase())
    : panePresets.some((p) => p.toLowerCase() === value.toLowerCase());
  const displayValue = value === "auto" ? "#000000" : value;
  const swatchStyle =
    value !== "auto" && (isPresetSelected || /^#[0-9A-Fa-f]{6}$/.test(value))
      ? { backgroundColor: displayValue }
      : {
          background: "linear-gradient(90deg, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000)"
        };

  return (
    <div className={cn("flex min-w-0 flex-wrap items-center gap-2", className)}>
      {outlineWithAuto && !hideAutoButton && (
        <button
          type="button"
          onClick={() => onOutlineAutoChange?.(!outlineAuto)}
          className={cn(
            "rounded-md border px-2 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            outlineAuto
              ? "border-foreground bg-accent text-accent-foreground"
              : "border-border bg-muted/50 text-muted-foreground hover:bg-muted"
          )}
        >
          Auto
        </button>
      )}
      {!compact &&
        panePresets.map((swatch) => (
          <button
            key={swatch}
            type="button"
            aria-label={`Select color ${swatch}`}
            className={cn(
              "h-6 w-6 shrink-0 rounded-full border-2 transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              value.toLowerCase() === swatch.toLowerCase() ? "border-foreground ring-2 ring-foreground/30" : "border-transparent"
            )}
            style={{ backgroundColor: swatch }}
            onClick={() => onChange(swatch)}
          />
        ))}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={compact ? "Open color picker" : "Custom color"}
            className={cn(
              "flex min-w-0 cursor-pointer items-center rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              compact ? "shrink-0" : "gap-1.5"
            )}
          >
            <div
              className="h-6 w-6 shrink-0 rounded border-2 border-border"
              style={swatchStyle}
              aria-hidden
            />
            {!compact && <span className="text-xs text-muted-foreground">Custom</span>}
          </button>
        </PopoverTrigger>
        <PopoverContent
          className="w-80 dark:bg-zinc-700 dark:border-zinc-600 dark:shadow-xl"
          align="start"
        >
          <ColorPopoverContent
            value={value === "auto" ? "#000000" : value}
            onChange={(hex) => {
              onChange(hex);
              if (outlineWithAuto && outlineAuto) onOutlineAutoChange?.(false);
            }}
            opacity={opacity}
            onOpacityChange={onOpacityChange ?? (() => {})}
            presets={presets}
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}
