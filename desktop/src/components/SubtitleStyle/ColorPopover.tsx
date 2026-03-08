import * as React from "react";

import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { OpacitySlider } from "@/components/ui/opacity-slider";
import { cn } from "@/lib/utils";
import {
  hexToHsv,
  hsvToHex,
  hexToRgb,
  rgbToHex,
  hexToHsl,
  hslToHex,
  SWATCH_SETS,
  type ColorKind
} from "./colorUtils";

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

type ColorPopoverContentProps = {
  value: string;
  onChange: (hex: string) => void;
  opacity: number;
  onOpacityChange: (opacity: number) => void;
  presets: readonly string[];
  onClose?: () => void;
};

function ColorPopoverContent({
  value,
  onChange,
  opacity,
  onOpacityChange,
  presets
}: ColorPopoverContentProps) {
  const validHex = HEX_RE.test(value) ? value : "#ffffff";
  const [hsv, setHsv] = React.useState(() => hexToHsv(validHex) ?? { h: 0, s: 1, v: 1 });
  const [format, setFormat] = React.useState<"hex" | "rgb" | "hsl">("hex");
  const [hexInput, setHexInput] = React.useState(validHex);
  const [rgbInput, setRgbInput] = React.useState(() => {
    const r = hexToRgb(validHex);
    return r ? `${r.r}, ${r.g}, ${r.b}` : "255, 255, 255";
  });
  const [hslInput, setHslInput] = React.useState(() => {
    const h = hexToHsl(validHex);
    return h ? `${Math.round(h.h)}, ${Math.round(h.s)}%, ${Math.round(h.l)}%` : "0, 0%, 100%";
  });
  const boxRef = React.useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = React.useState(false);

  React.useEffect(() => {
    if (HEX_RE.test(value)) {
      const next = hexToHsv(value);
      if (next) {
        setHsv(next);
        setHexInput(value);
        const r = hexToRgb(value);
        if (r) setRgbInput(`${r.r}, ${r.g}, ${r.b}`);
        const h = hexToHsl(value);
        if (h) setHslInput(`${Math.round(h.h)}, ${Math.round(h.s)}%, ${Math.round(h.l)}%`);
      }
    }
  }, [value]);

  const syncFromHsv = React.useCallback((h: number, s: number, v: number) => {
    const hex = hsvToHex(h, s, v);
    setHexInput(hex);
    const r = hexToRgb(hex);
    if (r) setRgbInput(`${r.r}, ${r.g}, ${r.b}`);
    const hl = hexToHsl(hex);
    if (hl) setHslInput(`${Math.round(hl.h)}, ${Math.round(hl.s)}%, ${Math.round(hl.l)}%`);
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
        syncFromHsv(next.h, next.s, next.v);
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
      syncFromHsv(next.h, next.s, next.v);
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

  const commitRgb = () => {
    const parts = rgbInput.split(",").map((p) => Number.parseInt(p.trim(), 10));
    if (parts.length === 3 && parts.every((n) => !Number.isNaN(n))) {
      const hex = rgbToHex(parts[0], parts[1], parts[2]);
      onChange(hex);
      const next = hexToHsv(hex);
      if (next) setHsv(next);
    }
  };

  const commitHsl = () => {
    const match = hslInput.match(/(\d+)\s*,\s*(\d+)%\s*,\s*(\d+)%/);
    if (match) {
      const hex = hslToHex(Number(match[1]), Number(match[2]), Number(match[3]));
      onChange(hex);
      const next = hexToHsv(hex);
      if (next) setHsv(next);
    }
  };

  const hueGradient = "linear-gradient(90deg, #ff0000 0%, #ffff00 17%, #00ff00 33%, #00ffff 50%, #0000ff 67%, #ff00ff 83%, #ff0000 100%)";

  return (
    <div className="space-y-3">
      <div
        ref={boxRef}
        className="relative h-32 w-full cursor-crosshair overflow-hidden rounded-md border border-border"
        style={{
          background: `
            linear-gradient(to bottom, transparent 0%, black 100%),
            linear-gradient(to right, white 0%, hsl(${hsv.h}, 100%, 50%) 100%)
          `
        }}
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
              syncFromHsv(next.h, next.s, next.v);
              return next;
            });
          }
          if (e.key === "ArrowRight") {
            e.preventDefault();
            setHsv((prev) => {
              const s = Math.min(1, prev.s + step / 100);
              const next = { ...prev, s };
              syncFromHsv(next.h, next.s, next.v);
              return next;
            });
          }
        }}
      >
        <div
          className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow"
          style={{
            left: `${hsv.s * 100}%`,
            top: `${(1 - hsv.v) * 100}%`,
            backgroundColor: hsvToHex(hsv.h, hsv.s, hsv.v)
          }}
        />
      </div>

      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">Hue</Label>
        <div
          className="relative h-3 w-full cursor-pointer overflow-hidden rounded-full border border-border"
          style={{ background: hueGradient }}
          onMouseDown={(e) => {
            e.preventDefault();
            const rect = e.currentTarget.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const h = x * 360;
            handleHueChange(h);
            const onMove = (ev: MouseEvent) => {
              const x2 = (ev.clientX - rect.left) / rect.width;
              handleHueChange(Math.max(0, Math.min(360, x2 * 360)));
            };
            const onUp = () => {
              window.removeEventListener("mousemove", onMove);
              window.removeEventListener("mouseup", onUp);
            };
            window.addEventListener("mousemove", onMove);
            window.addEventListener("mouseup", onUp);
          }}
        >
          <div
            className="absolute top-0 bottom-0 w-1 -translate-x-1/2 border border-white shadow"
            style={{ left: `${(hsv.h / 360) * 100}%` }}
          />
        </div>
      </div>

      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">Opacity</Label>
        <OpacitySlider
          min={0}
          max={100}
          step={1}
          value={[Math.round(opacity * 100)]}
          onValueChange={([v]) => onOpacityChange(v / 100)}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={format} onValueChange={(v) => setFormat(v as "hex" | "rgb" | "hsl")}>
          <SelectTrigger className="h-8 w-20 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="hex">HEX</SelectItem>
            <SelectItem value="rgb">RGB</SelectItem>
            <SelectItem value="hsl">HSL</SelectItem>
          </SelectContent>
        </Select>
        {format === "hex" && (
          <>
            <Input
              className="h-8 w-24 font-mono text-xs"
              value={hexInput}
              onChange={(e) => setHexInput(e.target.value)}
              onBlur={commitHex}
              onKeyDown={(e) => e.key === "Enter" && commitHex()}
            />
            <div
              className="h-6 w-6 shrink-0 rounded border border-border"
              style={{ backgroundColor: HEX_RE.test(hexInput) ? hexInput : "#fff" }}
              aria-hidden
            />
          </>
        )}
        {format === "rgb" && (
          <>
            <Input
              className="h-8 flex-1 font-mono text-xs"
              value={rgbInput}
              onChange={(e) => setRgbInput(e.target.value)}
              onBlur={commitRgb}
              onKeyDown={(e) => e.key === "Enter" && commitRgb()}
              placeholder="R, G, B"
            />
            <div
              className="h-6 w-6 shrink-0 rounded border border-border"
              style={{ backgroundColor: validHex }}
              aria-hidden
            />
          </>
        )}
        {format === "hsl" && (
          <>
            <Input
              className="h-8 flex-1 font-mono text-xs"
              value={hslInput}
              onChange={(e) => setHslInput(e.target.value)}
              onBlur={commitHsl}
              onKeyDown={(e) => e.key === "Enter" && commitHsl()}
              placeholder="H, S%, L%"
            />
            <div
              className="h-6 w-6 shrink-0 rounded border border-border"
              style={{ backgroundColor: validHex }}
              aria-hidden
            />
          </>
        )}
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">Presets</Label>
        <div className="flex flex-wrap gap-1.5">
          {presets.map((swatch) => (
            <button
              key={swatch}
              type="button"
              aria-label={`Select ${swatch}`}
              className={cn(
                "h-6 w-6 shrink-0 rounded-full border-2 transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                value.toLowerCase() === swatch.toLowerCase()
                  ? "border-foreground ring-2 ring-foreground/30"
                  : "border-transparent"
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
  const customSwatchStyle =
    value !== "auto" && (isPresetSelected || /^#[0-9A-Fa-f]{6}$/.test(value))
      ? { backgroundColor: value }
      : {
          background: "linear-gradient(90deg, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000)"
        };

  return (
    <div className={cn("flex min-w-0 flex-wrap items-center gap-2", className)}>
      {outlineWithAuto && (
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
      {panePresets.map((swatch) => (
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
            className="flex min-w-0 cursor-pointer items-center gap-1.5 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <div
              className="h-6 w-6 shrink-0 rounded border-2 border-border"
              style={customSwatchStyle}
              aria-hidden
            />
            <span className="text-xs text-muted-foreground">Custom</span>
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80" align="start">
          <Tabs defaultValue="solid">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="solid">Solid</TabsTrigger>
              <TabsTrigger value="linear">Linear</TabsTrigger>
            </TabsList>
            <TabsContent value="solid" className="mt-2">
              <ColorPopoverContent
                value={value === "auto" ? "#000000" : value}
                onChange={(hex) => {
                  onChange(hex);
                  if (outlineWithAuto && outlineAuto) onOutlineAutoChange?.(false);
                }}
                opacity={opacity}
                onOpacityChange={onOpacityChange ?? (() => {})}
                presets={presets}
                onClose={() => setOpen(false)}
              />
            </TabsContent>
            <TabsContent value="linear" className="mt-2">
              <p className="text-sm text-muted-foreground">Coming soon</p>
            </TabsContent>
          </Tabs>
        </PopoverContent>
      </Popover>
    </div>
  );
}
