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
import ColorSwatchInput from "./ColorSwatchInput";
import type { SubtitleStyleAppearance } from "@/settingsClient";

/* ---------- constants ---------- */

const HIGHLIGHT_SWATCHES = ["#FFD400", "#46D9FF", "#00FF66"];

const PRESET_OPTIONS: { value: string; label: string; disabled?: boolean }[] = [
  { value: "classic_static", label: "Classic (Static)" },
  { value: "bold_outline_static", label: "Bold Outline (Static)" },
  { value: "boxed_static", label: "Boxed (Static)" },
  { value: "neon_karaoke", label: "Neon Karaoke (Karaoke)" },
  { value: "boxed_karaoke", label: "Boxed Karaoke (Karaoke)" },
  { value: "Custom", label: "Custom", disabled: true }
];

const FONT_FAMILY_OPTIONS = [
  "Arial",
  "Helvetica",
  "DejaVu Sans",
  "Liberation Sans",
  "Noto Sans",
  "Sans Serif"
];

const FONT_STYLE_OPTIONS = [
  { value: "regular", label: "Regular" },
  { value: "bold", label: "Bold" },
  { value: "italic", label: "Italic" }
];

const TEXT_COLOR_SWATCHES = [
  "#FFFFFF",
  "#FFD400",
  "#46D9FF",
  "#00FF66",
  "#FF8A00",
  "#FF5AA5"
];

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

  const fontFamilyOptions = React.useMemo(() => {
    if (FONT_FAMILY_OPTIONS.includes(appearance.font_family)) {
      return FONT_FAMILY_OPTIONS;
    }
    return [appearance.font_family, ...FONT_FAMILY_OPTIONS];
  }, [appearance.font_family]);

  const textSummary = `${appearance.font_family} • ${appearance.font_size} • ${Math.round(appearance.text_opacity * 100)}% • Spacing ${appearance.letter_spacing}`;
  const outlineSummary =
    appearance.outline_width === 0
      ? "Off"
      : `${appearance.outline_width} • ${appearance.outline_color}`;
  const shadowSummary =
    appearance.shadow_strength === 0
      ? "Off"
      : `${appearance.shadow_strength} • X${appearance.shadow_offset_x} Y${appearance.shadow_offset_y} • ${Math.round(appearance.shadow_opacity * 100)}%`;
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
              <Select
                value={appearance.font_family}
                onValueChange={(v) => patch({ font_family: v })}
              >
                <SelectTrigger className="h-7 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {fontFamilyOptions.map((fontName) => (
                    <SelectItem key={fontName} value={fontName}>
                      {fontName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Style</Label>
              <Select
                value={appearance.font_style}
                onValueChange={(v) => patch({ font_style: v })}
              >
                <SelectTrigger className="h-7 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FONT_STYLE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <SliderRow
              label="Size"
              value={appearance.font_size}
              min={18}
              max={72}
              onChange={(v) => patch({ font_size: v })}
            />
            <SliderRow
              label="Letter spacing"
              value={appearance.letter_spacing}
              min={-5}
              max={20}
              step={0.5}
              onChange={(v) => patch({ letter_spacing: v })}
            />
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Text color</Label>
              <ColorSwatchInput
                value={appearance.text_color}
                onChange={(c) => patch({ text_color: c })}
                swatches={TEXT_COLOR_SWATCHES}
              />
            </div>
            <SliderRow
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
              <ColorSwatchInput
                value={appearance.outline_color}
                onChange={(c) => patch({ outline_color: c })}
                swatches={["#000000"]}
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
              <ColorSwatchInput
                value={appearance.shadow_color}
                onChange={(c) => patch({ shadow_color: c })}
                swatches={["#000000"]}
              />
            </div>
            <SliderRow
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
                <ColorSwatchInput
                  value={appearance.highlight_color}
                  onChange={(c) => patch({ highlight_color: c })}
                  swatches={HIGHLIGHT_SWATCHES}
                />
              </div>
              <SliderRow
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
                  <ColorSwatchInput
                    value={appearance.line_bg_color}
                    onChange={(c) => patch({ line_bg_color: c })}
                  />
                </div>
                <SliderRow
                  label="Background opacity"
                  value={Math.round(appearance.line_bg_opacity * 100)}
                  min={0}
                  max={100}
                  onChange={(v) => patch({ line_bg_opacity: v / 100 })}
                />
                <SliderRow
                  label="Padding"
                  value={appearance.line_bg_padding}
                  min={0}
                  max={40}
                  onChange={(v) => patch({ line_bg_padding: v })}
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
                  <ColorSwatchInput
                    value={appearance.word_bg_color}
                    onChange={(c) => patch({ word_bg_color: c })}
                  />
                </div>
                <SliderRow
                  label="Background opacity"
                  value={Math.round(appearance.word_bg_opacity * 100)}
                  min={0}
                  max={100}
                  onChange={(v) => patch({ word_bg_opacity: v / 100 })}
                />
                <SliderRow
                  label="Padding"
                  value={appearance.word_bg_padding}
                  min={0}
                  max={40}
                  onChange={(v) => patch({ word_bg_padding: v })}
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
