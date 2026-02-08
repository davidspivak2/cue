import * as React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import ColorSwatchInput from "./ColorSwatchInput";
import type { SubtitleStyleAppearance } from "@/settingsClient";

/* ---------- constants ---------- */

const HIGHLIGHT_SWATCHES = ["#FFD400", "#46D9FF", "#00FF66"];

const PRESET_OPTIONS = [
  { value: "Default", label: "Default" },
  { value: "Large outline", label: "Large outline" },
  { value: "Large outline + box", label: "Large outline + box" },
  { value: "Custom", label: "Custom" }
];

const FONT_STYLE_OPTIONS = [
  { value: "regular", label: "Regular" },
  { value: "bold", label: "Bold" },
  { value: "italic", label: "Italic" }
];

const VERTICAL_ANCHOR_OPTIONS = [
  { value: "bottom", label: "Bottom" },
  { value: "middle", label: "Middle" },
  { value: "top", label: "Top" }
];

/* ---------- helpers ---------- */

type SliderRowProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
};

const SliderRow = ({ label, value, min, max, step = 1, onChange }: SliderRowProps) => (
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
  </div>
);

const SectionHeading = ({ children }: { children: React.ReactNode }) => (
  <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
    {children}
  </h3>
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
  const [advancedOpen, setAdvancedOpen] = React.useState(false);

  const patch = (changes: Partial<SubtitleStyleAppearance>) => {
    onAppearanceChange(changes);
  };

  const isWordHighlight = appearance.subtitle_mode === "word_highlight";
  const bgMode = appearance.background_mode;

  return (
    <div className="space-y-5">
      {/* ── Section 1: Mode & Preset ── */}
      <section className="space-y-3">
        <SectionHeading>Mode</SectionHeading>
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
              Word highlight
            </Label>
          </div>
        </RadioGroup>

        {isWordHighlight && (
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Highlight color</Label>
            <ColorSwatchInput
              value={appearance.highlight_color}
              onChange={(c) => patch({ highlight_color: c })}
              swatches={HIGHLIGHT_SWATCHES}
            />
            <SliderRow
              label="Highlight opacity"
              value={Math.round(highlightOpacity * 100)}
              min={0}
              max={100}
              onChange={(v) => onHighlightOpacityChange(v / 100)}
            />
          </div>
        )}

        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1.5">
            <Label className="text-xs text-muted-foreground">Preset</Label>
            <Select value={preset} onValueChange={onPresetChange}>
              <SelectTrigger className="h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PRESET_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={onResetPreset}
          >
            Reset
          </Button>
        </div>
      </section>

      {/* ── Section 2: Quick Settings ── */}
      <section className="space-y-3">
        <SectionHeading>Quick settings</SectionHeading>
        <SliderRow
          label="Font size"
          value={appearance.font_size}
          min={18}
          max={72}
          onChange={(v) => patch({ font_size: v })}
        />
        <SliderRow
          label="Outline"
          value={appearance.outline_width}
          min={0}
          max={10}
          onChange={(v) =>
            patch({ outline_width: v, outline_enabled: v > 0 })
          }
        />
        <SliderRow
          label="Shadow"
          value={appearance.shadow_strength}
          min={0}
          max={10}
          onChange={(v) =>
            patch({ shadow_strength: v, shadow_enabled: v > 0 })
          }
        />
        <SliderRow
          label="Bottom margin"
          value={appearance.vertical_offset}
          min={0}
          max={200}
          onChange={(v) => patch({ vertical_offset: v })}
        />
      </section>

      {/* ── Section 3: Background ── */}
      <section className="space-y-3">
        <SectionHeading>Background</SectionHeading>
        <RadioGroup
          value={bgMode}
          onValueChange={(v) => patch({ background_mode: v })}
          className="flex gap-3"
        >
          <div className="flex items-center gap-1.5">
            <RadioGroupItem id="bg-none" value="none" />
            <Label htmlFor="bg-none" className="text-sm">None</Label>
          </div>
          <div className="flex items-center gap-1.5">
            <RadioGroupItem id="bg-line" value="line" />
            <Label htmlFor="bg-line" className="text-sm">Around line</Label>
          </div>
          <div className="flex items-center gap-1.5">
            <RadioGroupItem id="bg-word" value="word" />
            <Label htmlFor="bg-word" className="text-sm">Around word</Label>
          </div>
        </RadioGroup>

        {bgMode === "line" && (
          <div className="space-y-2 rounded-md border border-border p-3">
            <Label className="text-xs text-muted-foreground">Line background</Label>
            <ColorSwatchInput
              value={appearance.line_bg_color}
              onChange={(c) => patch({ line_bg_color: c })}
            />
            <SliderRow
              label="Opacity"
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
          <div className="space-y-2 rounded-md border border-border p-3">
            <Label className="text-xs text-muted-foreground">Word background</Label>
            <ColorSwatchInput
              value={appearance.word_bg_color}
              onChange={(c) => patch({ word_bg_color: c })}
            />
            <SliderRow
              label="Opacity"
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
      </section>

      {/* ── Section 4: Advanced ── */}
      <section className="space-y-3">
        <button
          type="button"
          className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          onClick={() => setAdvancedOpen((v) => !v)}
        >
          {advancedOpen ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          Advanced
        </button>

        {advancedOpen && (
          <div className="space-y-4">
            {/* Text */}
            <div className="space-y-2 rounded-md border border-border p-3">
              <Label className="text-xs font-medium">Text</Label>
              <div className="space-y-2">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Font family</Label>
                  <Input
                    className="h-7 text-xs"
                    value={appearance.font_family}
                    onChange={(e) => patch({ font_family: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Font style</Label>
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
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Text color</Label>
                  <ColorSwatchInput
                    value={appearance.text_color}
                    onChange={(c) => patch({ text_color: c })}
                    swatches={["#FFFFFF", "#000000"]}
                  />
                </div>
                <SliderRow
                  label="Text opacity"
                  value={Math.round(appearance.text_opacity * 100)}
                  min={10}
                  max={100}
                  onChange={(v) => patch({ text_opacity: v / 100 })}
                />
                <SliderRow
                  label="Letter spacing"
                  value={appearance.letter_spacing}
                  min={-5}
                  max={20}
                  step={0.5}
                  onChange={(v) => patch({ letter_spacing: v })}
                />
              </div>
            </div>

            {/* Outline */}
            <div className="space-y-2 rounded-md border border-border p-3">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="outline-enabled"
                  checked={appearance.outline_enabled}
                  onCheckedChange={(c) =>
                    patch({ outline_enabled: Boolean(c) })
                  }
                />
                <Label htmlFor="outline-enabled" className="text-xs font-medium">
                  Outline
                </Label>
              </div>
              {appearance.outline_enabled && (
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Outline color</Label>
                  <ColorSwatchInput
                    value={appearance.outline_color}
                    onChange={(c) => patch({ outline_color: c })}
                    swatches={["#000000"]}
                  />
                </div>
              )}
            </div>

            {/* Shadow */}
            <div className="space-y-2 rounded-md border border-border p-3">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="shadow-enabled"
                  checked={appearance.shadow_enabled}
                  onCheckedChange={(c) =>
                    patch({ shadow_enabled: Boolean(c) })
                  }
                />
                <Label htmlFor="shadow-enabled" className="text-xs font-medium">
                  Shadow
                </Label>
              </div>
              {appearance.shadow_enabled && (
                <div className="space-y-2">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Shadow color</Label>
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
                </div>
              )}
            </div>

            {/* Vertical position */}
            <div className="space-y-2 rounded-md border border-border p-3">
              <Label className="text-xs font-medium">Vertical position</Label>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Anchor</Label>
                <Select
                  value={appearance.vertical_anchor}
                  onValueChange={(v) => patch({ vertical_anchor: v })}
                >
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {VERTICAL_ANCHOR_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <SliderRow
                label="Vertical offset"
                value={appearance.vertical_offset}
                min={0}
                max={200}
                onChange={(v) => patch({ vertical_offset: v })}
              />
            </div>
          </div>
        )}
      </section>
    </div>
  );
};

export default StyleControls;
