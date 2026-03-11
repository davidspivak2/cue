import * as React from "react";

import { Link, Unlink } from "lucide-react";

import { ColorRow } from "./ColorPopover";
import SubtitleTextControls, {
  findFontMetadata,
  getFontWeightLabel,
  isItalicFontStyle,
  normalizeFontWeight
} from "./SubtitleTextControls";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { OpacitySlider } from "@/components/ui/opacity-slider";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import type {
  SubtitleFontMetadata,
  SubtitleStyleAppearance
} from "@/settingsClient";

const PRESET_OPTIONS: { value: string; label: string; disabled?: boolean }[] = [
  { value: "classic_static", label: "Classic (Static)" },
  { value: "bold_outline_static", label: "Bold Outline (Static)" },
  { value: "boxed_static", label: "Boxed (Static)" },
  { value: "lift_static", label: "Lift (Static)" },
  { value: "neon_karaoke", label: "Neon Karaoke (Karaoke)" },
  { value: "boxed_karaoke", label: "Boxed Karaoke (Karaoke)" },
  { value: "Custom", label: "Custom", disabled: true }
];

const PADDING_MIN = 0;
const PADDING_MAX = 40;
const PADDING_STEP = 1;

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
        className="h-7 w-12 px-2 text-center text-xs"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (!Number.isNaN(n)) onChange(Math.min(max, Math.max(min, n)));
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
    <Input
      type="number"
      className="h-7 w-12 px-2 text-center text-xs"
      min={min}
      max={max}
      step={1}
      value={Math.round(value)}
      onChange={(e) => {
        const n = Number(e.target.value);
        if (!Number.isNaN(n)) onChange(Math.min(max, Math.max(min, n)));
      }}
    />
  </div>
);

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
            className="h-7 w-12 px-2 text-center text-xs"
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
                className="h-7 w-12 px-1.5 text-center text-xs"
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

export type StyleControlsProps = {
  appearance: SubtitleStyleAppearance;
  fonts: SubtitleFontMetadata[];
  fontsLoading: boolean;
  fontsError: string | null;
  preset: string;
  highlightOpacity: number;
  showAnimationControl?: boolean;
  showHighlightSection?: boolean;
  showTextSection?: boolean;
  onAppearanceChange: (changes: Partial<SubtitleStyleAppearance>) => void;
  onPresetChange: (preset: string) => void;
  onHighlightOpacityChange: (opacity: number) => void;
  onResetPreset: () => void;
};

const StyleControls = ({
  appearance,
  fonts,
  fontsLoading,
  fontsError,
  preset,
  highlightOpacity,
  showAnimationControl = true,
  showHighlightSection = true,
  showTextSection = true,
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
  const currentFontWeight = React.useMemo(
    () => normalizeFontWeight(appearance.font_weight),
    [appearance.font_weight]
  );
  const italicActive = isItalicFontStyle(appearance.font_style);
  const matchedFont = React.useMemo(
    () => findFontMetadata(fonts, appearance.font_family),
    [appearance.font_family, fonts]
  );
  const selectedFont =
    matchedFont ?? {
      family: appearance.font_family || "Unknown font"
    };
  const isCurrentFontUnavailable =
    !fontsLoading && !fontsError && matchedFont === null;

  React.useEffect(() => {
    if (!isWordHighlight && bgMode === "word") {
      patch({ background_mode: "none" });
    }
  }, [bgMode, isWordHighlight]); // eslint-disable-line react-hooks/exhaustive-deps

  const textSummary = `${selectedFont.family}${isCurrentFontUnavailable ? " unavailable" : ""} | ${getFontWeightLabel(currentFontWeight)} | ${italicActive ? "Italic" : "Regular"} | ${appearance.font_size} | ${Math.round(appearance.text_opacity * 100)}%`;
  const outlineSummary =
    appearance.outline_width === 0
      ? "Off"
      : appearance.outline_color === "auto"
        ? `${appearance.outline_width} | Auto`
        : `${appearance.outline_width} | ${appearance.outline_color}`;
  const shadowBlur = appearance.shadow_blur ?? 10;
  const shadowSummary = !appearance.shadow_enabled
    ? "Off"
    : `Blur ${shadowBlur} | X${appearance.shadow_offset_x} Y${appearance.shadow_offset_y} | ${Math.round(appearance.shadow_opacity * 100)}%`;
  const highlightSummary = `${appearance.highlight_color} | ${Math.round(highlightOpacity * 100)}%`;
  const backgroundOpacity =
    bgMode === "line"
      ? Math.round(appearance.line_bg_opacity * 100)
      : bgMode === "word"
        ? Math.round(appearance.word_bg_opacity * 100)
        : 0;
  const backgroundSummary =
    bgMode === "none"
      ? "None"
      : `${bgMode === "line" ? "Line" : "Word"} | ${backgroundOpacity}%`;

  return (
    <div className="space-y-4">
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

        {showAnimationControl && (
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
        )}
      </section>

      <Accordion
        type="multiple"
        defaultValue={showTextSection ? ["text"] : ["outline"]}
        className="rounded-md border border-border"
      >
        {showTextSection && (
          <AccordionItem value="text">
            <AccordionTrigger className="px-3 hover:no-underline">
              <span className="flex flex-col items-start gap-0.5">
                <span className="font-medium">Text</span>
                <span className="text-xs font-normal text-muted-foreground">
                  {textSummary}
                </span>
              </span>
            </AccordionTrigger>
            <AccordionContent className="px-3">
              <SubtitleTextControls
                appearance={appearance}
                fonts={fonts}
                fontsLoading={fontsLoading}
                fontsError={fontsError}
                highlightOpacity={highlightOpacity}
                onAppearanceChange={onAppearanceChange}
                onHighlightOpacityChange={onHighlightOpacityChange}
              />
            </AccordionContent>
          </AccordionItem>
        )}

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
              min={1}
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
        {showHighlightSection && isWordHighlight && (
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
                  <Label htmlFor="bg-none" className="whitespace-nowrap text-xs">
                    None
                  </Label>
                </div>
                <div className="flex items-center gap-1.5">
                  <RadioGroupItem id="bg-line" value="line" />
                  <Label htmlFor="bg-line" className="whitespace-nowrap text-xs">
                    Line
                  </Label>
                </div>
                {isWordHighlight && (
                  <div className="flex items-center gap-1.5">
                    <RadioGroupItem id="bg-word" value="word" />
                    <Label htmlFor="bg-word" className="whitespace-nowrap text-xs">
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
                  label="Corner roundness"
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
                  label="Corner roundness"
                  value={appearance.word_bg_radius}
                  min={0}
                  max={40}
                  onChange={(v) => patch({ word_bg_radius: v })}
                />
              </div>
            )}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
};

export default StyleControls;
