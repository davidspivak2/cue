import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "@/components/ui/accordion";
import { ChevronDown, Link, Unlink } from "lucide-react";
import { ColorRow } from "./ColorPopover";
import { OpacitySlider } from "@/components/ui/opacity-slider";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { SubtitleStyleAppearance } from "@/settingsClient";

/* ---------- constants ---------- */

const PRESET_OPTIONS: { value: string; label: string; disabled?: boolean }[] = [
  { value: "classic_static", label: "Classic (Static)" },
  { value: "bold_outline_static", label: "Bold Outline (Static)" },
  { value: "boxed_static", label: "Boxed (Static)" },
  { value: "lift_static", label: "Lift (Static)" },
  { value: "neon_karaoke", label: "Neon Karaoke (Karaoke)" },
  { value: "boxed_karaoke", label: "Boxed Karaoke (Karaoke)" },
  { value: "Custom", label: "Custom", disabled: true }
];

const CURATED_FONTS = [
  "Heebo",
  "Assistant",
  "Rubik",
  "IBM Plex Sans Hebrew",
  "Noto Sans Hebrew",
  "Alef",
  "Arimo",
  "Secular One",
  "Suez One",
  "Frank Ruhl Libre"
] as const;


const POSITION_ANCHOR_OPTIONS = [
  { value: "bottom", label: "Bottom" },
  { value: "middle", label: "Middle" },
  { value: "top", label: "Top" }
] as const;

/* ---------- helpers ---------- */

type SliderRowProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  valueSuffix?: string;
};

const SliderRow = ({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  valueSuffix
}: SliderRowProps) => (
  <div className="grid grid-cols-[1fr_auto] items-center gap-3">
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={([v]) => onChange(v)}
      />
    </div>
    <div className="flex items-center gap-1.5">
      <Input
        type="number"
        className="h-7 w-16 px-2 text-xs"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (!Number.isNaN(n)) {
            onChange(Math.min(max, Math.max(min, n)));
          }
        }}
      />
      {valueSuffix && (
        <span className="text-xs text-muted-foreground">{valueSuffix}</span>
      )}
    </div>
  </div>
);

type OpacityRowProps = {
  label: string;
  value: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
};

const OpacityRow = ({
  label,
  value,
  min = 0,
  max = 100,
  onChange
}: OpacityRowProps) => (
  <div className="grid grid-cols-[1fr_auto] items-center gap-3">
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <OpacitySlider
        min={min}
        max={max}
        step={1}
        value={[Math.round(value)]}
        onValueChange={([v]) => onChange(v)}
      />
    </div>
    <div className="flex items-center gap-1.5">
      <Input
        type="number"
        className="h-7 w-16 px-2 text-xs"
        min={min}
        max={max}
        step={1}
        value={Math.round(value)}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (!Number.isNaN(n)) {
            onChange(Math.min(max, Math.max(min, n)));
          }
        }}
      />
      <span className="text-xs text-muted-foreground">%</span>
    </div>
  </div>
);

const PADDING_MIN = 0;
const PADDING_MAX = 40;
const PADDING_STEP = 1;

type PaddingRowProps = {
  label: string;
  top: number;
  right: number;
  bottom: number;
  left: number;
  linked: boolean;
  onToggleLink: () => void;
  onLinkedChange: (v: number) => void;
  onTopChange: (v: number) => void;
  onRightChange: (v: number) => void;
  onBottomChange: (v: number) => void;
  onLeftChange: (v: number) => void;
};

const PaddingRow = ({
  label,
  top,
  right,
  bottom,
  left,
  linked,
  onToggleLink,
  onLinkedChange,
  onTopChange,
  onRightChange,
  onBottomChange,
  onLeftChange
}: PaddingRowProps) => {
  const clamp = (v: number) =>
    Math.min(PADDING_MAX, Math.max(PADDING_MIN, v));
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-xs text-muted-foreground">{label}</Label>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onToggleLink}
          title={linked ? "Unlink padding" : "Link padding"}
          aria-label={linked ? "Unlink padding" : "Link padding"}
        >
          {linked ? (
            <Link className="h-3.5 w-3.5" />
          ) : (
            <Unlink className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
      {linked ? (
        <div className="grid grid-cols-[1fr_auto] items-center gap-3">
          <Slider
            min={PADDING_MIN}
            max={PADDING_MAX}
            step={PADDING_STEP}
            value={[top]}
            onValueChange={([v]) => onLinkedChange(clamp(v))}
          />
          <Input
            type="number"
            className="h-7 w-16 px-2 text-xs"
            min={PADDING_MIN}
            max={PADDING_MAX}
            step={PADDING_STEP}
            value={top}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (!Number.isNaN(n)) onLinkedChange(clamp(n));
            }}
          />
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-1.5">
          {[
            { sub: "T", value: top, onChange: onTopChange },
            { sub: "R", value: right, onChange: onRightChange },
            { sub: "B", value: bottom, onChange: onBottomChange },
            { sub: "L", value: left, onChange: onLeftChange }
          ].map(({ sub, value, onChange }) => (
            <div key={sub} className="space-y-0.5">
              <Label className="text-[10px] text-muted-foreground">{sub}</Label>
              <Input
                type="number"
                className="h-7 px-1.5 text-xs"
                min={PADDING_MIN}
                max={PADDING_MAX}
                step={PADDING_STEP}
                value={value}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (!Number.isNaN(n)) onChange(clamp(n));
                }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ---------- props ---------- */

export type StyleControlsProps = {
  appearance: SubtitleStyleAppearance;
  preset: string;
  highlightOpacity: number;
  onAppearanceChange: (changes: Partial<SubtitleStyleAppearance>) => void;
  onPresetChange: (preset: string) => void;
  onHighlightOpacityChange: (opacity: number) => void;
  onResetPreset: () => void;
};

/* ---------- component ---------- */

const StyleControls = ({
  appearance,
  preset,
  highlightOpacity,
  onAppearanceChange,
  onPresetChange,
  onHighlightOpacityChange,
  onResetPreset
}: StyleControlsProps) => {
  const [fontSearchQuery, setFontSearchQuery] = React.useState("");
  const [fontOpen, setFontOpen] = React.useState(false);

  const patch = (changes: Partial<SubtitleStyleAppearance>) => {
    onAppearanceChange(changes);
  };

  const isWordHighlight = appearance.subtitle_mode === "word_highlight";
  const bgMode = appearance.background_mode;

  React.useEffect(() => {
    if (!isWordHighlight && bgMode === "word") {
      patch({ background_mode: "none" });
    }
  }, [bgMode, isWordHighlight]); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredFonts = React.useMemo(() => {
    const q = fontSearchQuery.trim().toLowerCase();
    if (!q) return [...CURATED_FONTS];
    return CURATED_FONTS.filter((f) => f.toLowerCase().includes(q));
  }, [fontSearchQuery]);

  const textSummary = `${appearance.font_family} • ${appearance.font_size} • ${Math.round(appearance.text_opacity * 100)}% • Spacing ${appearance.letter_spacing}`;
  const outlineSummary =
    appearance.outline_width === 0
      ? "Off"
      : appearance.outline_color === "auto"
        ? `${appearance.outline_width} • Auto`
        : `${appearance.outline_width} • ${appearance.outline_color}`;
  const shadowBlur = appearance.shadow_blur ?? 6;
  const shadowSummary =
    appearance.shadow_strength === 0
      ? "Off"
      : `Blur ${shadowBlur} • X${appearance.shadow_offset_x} Y${appearance.shadow_offset_y} • ${Math.round(appearance.shadow_opacity * 100)}%`;
  const highlightSummary = `${appearance.highlight_color} • ${Math.round(highlightOpacity * 100)}%`;
  const backgroundOpacity =
    bgMode === "line"
      ? Math.round(appearance.line_bg_opacity * 100)
      : bgMode === "word"
        ? Math.round(appearance.word_bg_opacity * 100)
        : 0;
  const backgroundSummary =
    bgMode === "none" ? "None" : `${bgMode === "line" ? "Line" : "Word"} • ${backgroundOpacity}%`;
  const positionSummary = `${appearance.vertical_anchor.charAt(0).toUpperCase() + appearance.vertical_anchor.slice(1)} • ${appearance.vertical_offset}`;

  const offsetLabel =
    appearance.vertical_anchor === "bottom"
      ? "Offset from bottom"
      : appearance.vertical_anchor === "top"
        ? "Offset from top"
        : "Offset from center";

  return (
    <div className="space-y-4">
      {/* ── Essentials (always visible) ── */}
      <section className="space-y-3">
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1.5">
            <Label className="text-xs text-muted-foreground">Preset</Label>
            <Select value={preset} onValueChange={onPresetChange}>
              <SelectTrigger className="h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PRESET_OPTIONS.map((opt) => (
                  <SelectItem
                    key={opt.value}
                    value={opt.value}
                    disabled={opt.disabled}
                  >
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="secondary" size="sm" onClick={onResetPreset}>
            Reset
          </Button>
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Animation</Label>
          <RadioGroup
            value={appearance.subtitle_mode}
            onValueChange={(v) => patch({ subtitle_mode: v })}
            className="flex gap-3"
          >
            <div className="flex items-center gap-1.5">
              <RadioGroupItem id="mode-static" value="static" />
              <Label htmlFor="mode-static" className="text-sm">
                Static
              </Label>
            </div>
            <div className="flex items-center gap-1.5">
              <RadioGroupItem id="mode-highlight" value="word_highlight" />
              <Label htmlFor="mode-highlight" className="text-sm">
                Karaoke
              </Label>
            </div>
          </RadioGroup>
        </div>
      </section>

      {/* ── Accordion groups ── */}
      <Accordion
        type="multiple"
        defaultValue={["text", "position"]}
        className="rounded-md border border-border"
      >
        <AccordionItem value="text">
          <AccordionTrigger className="px-3 hover:no-underline">
            <span className="flex flex-col items-start gap-0.5">
              <span className="font-medium">Text</span>
              <span className="text-xs font-normal text-muted-foreground">
                {textSummary}
              </span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-3 px-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Font</Label>
              <Popover open={fontOpen} onOpenChange={(o) => { setFontOpen(o); if (!o) setFontSearchQuery(""); }}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="h-7 w-full justify-between text-xs font-normal"
                  >
                    <span className="truncate">{appearance.font_family}</span>
                    <ChevronDown className="size-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
                  <Input
                    placeholder="Search fonts..."
                    className="h-8 border-0 border-b rounded-none focus-visible:ring-0"
                    value={fontSearchQuery}
                    onChange={(e) => setFontSearchQuery(e.target.value)}
                  />
                  <ScrollArea className="h-[200px]">
                    <div className="p-1">
                      {filteredFonts.map((fontName) => (
                        <button
                          key={fontName}
                          type="button"
                          className="flex w-full cursor-pointer items-center rounded-sm px-2 py-1.5 text-left text-xs hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground focus:outline-none"
                          onClick={() => {
                            patch({ font_family: fontName });
                            setFontOpen(false);
                            setFontSearchQuery("");
                          }}
                        >
                          {fontName}
                        </button>
                      ))}
                      {filteredFonts.length === 0 && (
                        <div className="py-2 text-center text-xs text-muted-foreground">No matches</div>
                      )}
                    </div>
                  </ScrollArea>
                </PopoverContent>
              </Popover>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Style</Label>
              <ToggleGroup
                type="multiple"
                value={
                  appearance.font_style === "bold_italic"
                    ? ["bold", "italic"]
                    : appearance.font_style === "bold"
                      ? ["bold"]
                      : appearance.font_style === "italic"
                        ? ["italic"]
                        : []
                }
                onValueChange={(v) => {
                  const style =
                    v.includes("bold") && v.includes("italic")
                      ? "bold_italic"
                      : v.includes("bold")
                        ? "bold"
                        : v.includes("italic")
                          ? "italic"
                          : "regular";
                  patch({ font_style: style });
                }}
                className="flex gap-1"
              >
                <ToggleGroupItem value="bold" aria-label="Bold" className="h-7 w-8 text-xs">
                  B
                </ToggleGroupItem>
                <ToggleGroupItem value="italic" aria-label="Italic" className="h-7 w-8 text-xs">
                  I
                </ToggleGroupItem>
              </ToggleGroup>
            </div>
            <SliderRow
              label="Size"
              value={appearance.font_size}
              min={18}
              max={72}
              onChange={(v) => patch({ font_size: v })}
            />
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Letter spacing</Label>
              <p className="text-[10px] text-muted-foreground">Adjust space between letters</p>
              <div className="grid grid-cols-[1fr_auto] items-center gap-3">
                <Slider
                  min={-5}
                  max={20}
                  step={0.5}
                  value={[appearance.letter_spacing]}
                  onValueChange={([v]) => patch({ letter_spacing: v })}
                />
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    className="h-7 w-16 px-2 text-xs"
                    min={-5}
                    max={20}
                    step={0.5}
                    value={appearance.letter_spacing}
                    onChange={(e) => {
                      const n = Number(e.target.value);
                      if (!Number.isNaN(n)) {
                        patch({ letter_spacing: Math.min(20, Math.max(-5, n)) });
                      }
                    }}
                  />
                </div>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Text color</Label>
              <ColorRow
                kind="text"
                value={appearance.text_color}
                onChange={(c) => patch({ text_color: c })}
                opacity={appearance.text_opacity}
                onOpacityChange={(o) => patch({ text_opacity: o })}
              />
            </div>
            <OpacityRow
              label="Opacity"
              value={Math.round(appearance.text_opacity * 100)}
              min={10}
              max={100}
              onChange={(v) => patch({ text_opacity: v / 100 })}
            />
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="outline">
          <AccordionTrigger className="px-3 hover:no-underline">
            <span className="flex flex-col items-start gap-0.5">
              <span className="font-medium">Outline</span>
              <span className="text-xs font-normal text-muted-foreground">
                {outlineSummary}
              </span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-3 px-3">
            <SliderRow
              label="Outline width"
              value={appearance.outline_width}
              min={0}
              max={10}
              step={0.5}
              onChange={(v) =>
                patch({ outline_width: v, outline_enabled: v > 0 })
              }
              valueSuffix={appearance.outline_width === 0 ? "Off" : undefined}
            />
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Outline color
              </Label>
              <ColorRow
                kind="outline"
                value={appearance.outline_color}
                onChange={(c) => patch({ outline_color: c })}
                outlineAuto={appearance.outline_color === "auto"}
                onOutlineAutoChange={(auto) =>
                  patch({
                    outline_color: auto
                      ? "auto"
                      : appearance.outline_color === "auto"
                        ? "#000000"
                        : appearance.outline_color
                  })
                }
              />
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="shadow">
          <AccordionTrigger className="px-3 hover:no-underline">
            <span className="flex flex-col items-start gap-0.5">
              <span className="font-medium">Shadow</span>
              <span className="text-xs font-normal text-muted-foreground">
                {shadowSummary}
              </span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-3 px-3">
            <SliderRow
              label="Shadow strength"
              value={appearance.shadow_strength}
              min={0}
              max={10}
              onChange={(v) =>
                patch({ shadow_strength: v, shadow_enabled: v > 0 })
              }
              valueSuffix={appearance.shadow_strength === 0 ? "Off" : undefined}
            />
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Shadow color
              </Label>
              <ColorRow
                kind="shadow"
                value={appearance.shadow_color}
                onChange={(c) => patch({ shadow_color: c })}
                opacity={appearance.shadow_opacity}
                onOpacityChange={(o) => patch({ shadow_opacity: o })}
              />
            </div>
            <OpacityRow
              label="Shadow opacity"
              value={Math.round(appearance.shadow_opacity * 100)}
              min={0}
              max={100}
              onChange={(v) => patch({ shadow_opacity: v / 100 })}
            />
            <SliderRow
              label="Shadow offset X"
              value={appearance.shadow_offset_x}
              min={-10}
              max={10}
              step={0.5}
              onChange={(v) => patch({ shadow_offset_x: v })}
            />
            <SliderRow
              label="Shadow offset Y"
              value={appearance.shadow_offset_y}
              min={-10}
              max={10}
              step={0.5}
              onChange={(v) => patch({ shadow_offset_y: v })}
            />
            <SliderRow
              label="Shadow blur"
              value={shadowBlur}
              min={0}
              max={20}
              step={1}
              onChange={(v) => patch({ shadow_blur: v })}
            />
          </AccordionContent>
        </AccordionItem>

        {isWordHighlight && (
          <AccordionItem value="highlight">
            <AccordionTrigger className="px-3 hover:no-underline">
              <span className="flex flex-col items-start gap-0.5">
                <span className="font-medium">Highlight</span>
                <span className="text-xs font-normal text-muted-foreground">
                  {highlightSummary}
                </span>
              </span>
            </AccordionTrigger>
            <AccordionContent className="space-y-3 px-3">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">
                  Highlight color
                </Label>
                <ColorRow
                  kind="highlight"
                  value={appearance.highlight_color}
                  onChange={(c) => patch({ highlight_color: c })}
                  opacity={highlightOpacity}
                  onOpacityChange={onHighlightOpacityChange}
                />
              </div>
              <OpacityRow
                label="Highlight opacity"
                value={Math.round(highlightOpacity * 100)}
                min={0}
                max={100}
                onChange={(v) => onHighlightOpacityChange(v / 100)}
              />
            </AccordionContent>
          </AccordionItem>
        )}

        <AccordionItem value="background">
          <AccordionTrigger className="px-3 hover:no-underline">
            <span className="flex flex-col items-start gap-0.5">
              <span className="font-medium">Background</span>
              <span className="text-xs font-normal text-muted-foreground">
                {backgroundSummary}
              </span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-3 px-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Background</Label>
              <RadioGroup
                value={bgMode}
                onValueChange={(v) => patch({ background_mode: v })}
                className="grid grid-cols-3 gap-2"
              >
                <div className="flex items-center gap-1.5">
                  <RadioGroupItem id="bg-none" value="none" />
                  <Label
                    htmlFor="bg-none"
                    className="whitespace-nowrap text-xs"
                  >
                    None
                  </Label>
                </div>
                <div className="flex items-center gap-1.5">
                  <RadioGroupItem id="bg-line" value="line" />
                  <Label
                    htmlFor="bg-line"
                    className="whitespace-nowrap text-xs"
                  >
                    Line
                  </Label>
                </div>
                {isWordHighlight && (
                  <div className="flex items-center gap-1.5">
                    <RadioGroupItem id="bg-word" value="word" />
                    <Label
                      htmlFor="bg-word"
                      className="whitespace-nowrap text-xs"
                    >
                      Word
                    </Label>
                  </div>
                )}
              </RadioGroup>
            </div>
            {bgMode === "line" && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">
                    Background color
                  </Label>
                  <ColorRow
                    kind="background"
                    value={appearance.line_bg_color}
                    onChange={(c) => patch({ line_bg_color: c })}
                    opacity={appearance.line_bg_opacity}
                    onOpacityChange={(o) => patch({ line_bg_opacity: o })}
                  />
                </div>
                <OpacityRow
                  label="Background opacity"
                  value={Math.round(appearance.line_bg_opacity * 100)}
                  min={0}
                  max={100}
                  onChange={(v) => patch({ line_bg_opacity: v / 100 })}
                />
                <PaddingRow
                  label="Padding"
                  top={appearance.line_bg_padding_top ?? appearance.line_bg_padding ?? 8}
                  right={appearance.line_bg_padding_right ?? appearance.line_bg_padding ?? 8}
                  bottom={appearance.line_bg_padding_bottom ?? appearance.line_bg_padding ?? 8}
                  left={appearance.line_bg_padding_left ?? appearance.line_bg_padding ?? 8}
                  linked={appearance.line_bg_padding_linked ?? true}
                  onToggleLink={() => {
                    const linked = appearance.line_bg_padding_linked ?? true;
                    const top = appearance.line_bg_padding_top ?? appearance.line_bg_padding ?? 8;
                    if (linked) {
                      patch({ line_bg_padding_linked: false });
                    } else {
                      patch({
                        line_bg_padding_linked: true,
                        line_bg_padding: top,
                        line_bg_padding_top: top,
                        line_bg_padding_right: top,
                        line_bg_padding_bottom: top,
                        line_bg_padding_left: top
                      });
                    }
                  }}
                  onLinkedChange={(v) =>
                    patch({
                      line_bg_padding: v,
                      line_bg_padding_top: v,
                      line_bg_padding_right: v,
                      line_bg_padding_bottom: v,
                      line_bg_padding_left: v
                    })
                  }
                  onTopChange={(v) => patch({ line_bg_padding_top: v })}
                  onRightChange={(v) => patch({ line_bg_padding_right: v })}
                  onBottomChange={(v) => patch({ line_bg_padding_bottom: v })}
                  onLeftChange={(v) => patch({ line_bg_padding_left: v })}
                />
                <SliderRow
                  label="Corner radius"
                  value={appearance.line_bg_radius}
                  min={0}
                  max={40}
                  onChange={(v) => patch({ line_bg_radius: v })}
                />
              </div>
            )}
            {bgMode === "word" && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">
                    Background color
                  </Label>
                  <ColorRow
                    kind="background"
                    value={appearance.word_bg_color}
                    onChange={(c) => patch({ word_bg_color: c })}
                    opacity={appearance.word_bg_opacity}
                    onOpacityChange={(o) => patch({ word_bg_opacity: o })}
                  />
                </div>
                <OpacityRow
                  label="Background opacity"
                  value={Math.round(appearance.word_bg_opacity * 100)}
                  min={0}
                  max={100}
                  onChange={(v) => patch({ word_bg_opacity: v / 100 })}
                />
                <PaddingRow
                  label="Padding"
                  top={appearance.word_bg_padding_top ?? appearance.word_bg_padding ?? 8}
                  right={appearance.word_bg_padding_right ?? appearance.word_bg_padding ?? 8}
                  bottom={appearance.word_bg_padding_bottom ?? appearance.word_bg_padding ?? 8}
                  left={appearance.word_bg_padding_left ?? appearance.word_bg_padding ?? 8}
                  linked={appearance.word_bg_padding_linked ?? true}
                  onToggleLink={() => {
                    const linked = appearance.word_bg_padding_linked ?? true;
                    const top = appearance.word_bg_padding_top ?? appearance.word_bg_padding ?? 8;
                    if (linked) {
                      patch({ word_bg_padding_linked: false });
                    } else {
                      patch({
                        word_bg_padding_linked: true,
                        word_bg_padding: top,
                        word_bg_padding_top: top,
                        word_bg_padding_right: top,
                        word_bg_padding_bottom: top,
                        word_bg_padding_left: top
                      });
                    }
                  }}
                  onLinkedChange={(v) =>
                    patch({
                      word_bg_padding: v,
                      word_bg_padding_top: v,
                      word_bg_padding_right: v,
                      word_bg_padding_bottom: v,
                      word_bg_padding_left: v
                    })
                  }
                  onTopChange={(v) => patch({ word_bg_padding_top: v })}
                  onRightChange={(v) => patch({ word_bg_padding_right: v })}
                  onBottomChange={(v) => patch({ word_bg_padding_bottom: v })}
                  onLeftChange={(v) => patch({ word_bg_padding_left: v })}
                />
                <SliderRow
                  label="Corner radius"
                  value={appearance.word_bg_radius}
                  min={0}
                  max={40}
                  onChange={(v) => patch({ word_bg_radius: v })}
                />
              </div>
            )}
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="position">
          <AccordionTrigger className="px-3 hover:no-underline">
            <span className="flex flex-col items-start gap-0.5">
              <span className="font-medium">Position</span>
              <span className="text-xs font-normal text-muted-foreground">
                {positionSummary}
              </span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-3 px-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Vertical position
              </Label>
              <ToggleGroup
                type="single"
                value={appearance.vertical_anchor}
                onValueChange={(v) => v && patch({ vertical_anchor: v })}
                className="grid grid-cols-3 gap-1"
              >
                {POSITION_ANCHOR_OPTIONS.map((opt) => (
                  <ToggleGroupItem
                    key={opt.value}
                    value={opt.value}
                    className="text-xs"
                    aria-label={opt.label}
                  >
                    {opt.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </div>
            <SliderRow
              label={offsetLabel}
              value={appearance.vertical_offset}
              min={0}
              max={200}
              onChange={(v) => patch({ vertical_offset: v })}
            />
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
};

export default StyleControls;
