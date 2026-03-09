import * as React from "react";

import { Link, Sparkles, Unlink } from "lucide-react";

import { ColorRow } from "./ColorPopover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { OpacitySlider } from "@/components/ui/opacity-slider";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import type { SubtitleStyleAppearance } from "@/settingsClient";

export type WorkbenchEffectId = "outline" | "shadow" | "background" | "karaoke";

type WorkbenchEffectsPanelProps = {
  appearance: SubtitleStyleAppearance;
  highlightOpacity: number;
  onAppearanceChange: (changes: Partial<SubtitleStyleAppearance>) => void;
  onHighlightOpacityChange: (opacity: number) => void;
  onToggleEffect: (effectId: WorkbenchEffectId) => void;
  onResetEffect: (effectId: WorkbenchEffectId) => void;
  onPreviewEffect: (effectId: WorkbenchEffectId | null) => void;
};

type SliderRowProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  valueSuffix?: string;
  inputTestId?: string;
};

type OpacityRowProps = {
  label: string;
  value: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
  inputTestId?: string;
};

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

type CardPreviewPayload = {
  appearance: SubtitleStyleAppearance;
  highlightOpacity: number;
};

const PADDING_MIN = 0;
const PADDING_MAX = 40;
const PADDING_STEP = 1;
const CARD_SAMPLE_TEXT = "Cue";

const SHADOW_DEFAULTS: Partial<SubtitleStyleAppearance> = {
  shadow_enabled: true,
  shadow_strength: 2,
  shadow_offset_x: 0,
  shadow_offset_y: 2,
  shadow_color: "#000000",
  shadow_opacity: 0.3,
  shadow_blur: 6
};

const effectOrder: WorkbenchEffectId[] = [
  "outline",
  "shadow",
  "background",
  "karaoke"
];

const effectLabels: Record<WorkbenchEffectId, string> = {
  outline: "Outline",
  shadow: "Shadow",
  background: "Background",
  karaoke: "Karaoke"
};

const effectDescriptions: Record<WorkbenchEffectId, string> = {
  outline: "Sharp text edge",
  shadow: "Depth and lift",
  background: "Line or word plate",
  karaoke: "Word-by-word glow"
};

const clampPadding = (value: number) =>
  Math.min(PADDING_MAX, Math.max(PADDING_MIN, value));

const isOutlineActive = (appearance: SubtitleStyleAppearance) =>
  appearance.outline_enabled && appearance.outline_width > 0;

const isShadowActive = (appearance: SubtitleStyleAppearance) =>
  appearance.shadow_enabled && appearance.shadow_strength > 0;

const isBackgroundActive = (appearance: SubtitleStyleAppearance) =>
  appearance.background_mode !== "none";

const isKaraokeActive = (appearance: SubtitleStyleAppearance) =>
  appearance.subtitle_mode === "word_highlight";

const isEffectActive = (
  effectId: WorkbenchEffectId,
  appearance: SubtitleStyleAppearance
) => {
  if (effectId === "outline") {
    return isOutlineActive(appearance);
  }
  if (effectId === "shadow") {
    return isShadowActive(appearance);
  }
  if (effectId === "background") {
    return isBackgroundActive(appearance);
  }
  return isKaraokeActive(appearance);
};

const buildOutlineShadows = (color: string, width: number) => {
  const shadows: string[] = [];
  for (let x = -1; x <= 1; x += 1) {
    for (let y = -1; y <= 1; y += 1) {
      if (x === 0 && y === 0) {
        continue;
      }
      shadows.push(`${x * width}px ${y * width}px 0 ${color}`);
    }
  }
  return shadows.join(", ");
};

const colorWithOpacity = (hex: string, opacity: number) => {
  const sanitized = /^#[0-9a-f]{6}$/i.test(hex) ? hex : "#000000";
  const r = Number.parseInt(sanitized.slice(1, 3), 16);
  const g = Number.parseInt(sanitized.slice(3, 5), 16);
  const b = Number.parseInt(sanitized.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(opacity, 1))})`;
};

const buildCardPreviewPayload = (
  effectId: WorkbenchEffectId,
  appearance: SubtitleStyleAppearance,
  highlightOpacity: number
): CardPreviewPayload => {
  const baseAppearance: SubtitleStyleAppearance = {
    ...appearance,
    outline_enabled: false,
    shadow_enabled: false,
    background_mode: "none",
    subtitle_mode: "static"
  };

  if (effectId === "outline") {
    return {
      appearance: {
        ...baseAppearance,
        outline_enabled: true,
        outline_width: isOutlineActive(appearance) ? appearance.outline_width : 2,
        outline_color:
          appearance.outline_color === "auto" ? "#000000" : appearance.outline_color
      },
      highlightOpacity
    };
  }

  if (effectId === "shadow") {
    return {
      appearance: {
        ...baseAppearance,
        shadow_enabled: true,
        shadow_strength: isShadowActive(appearance)
          ? appearance.shadow_strength
          : (SHADOW_DEFAULTS.shadow_strength as number),
        shadow_offset_x: isShadowActive(appearance)
          ? appearance.shadow_offset_x
          : (SHADOW_DEFAULTS.shadow_offset_x as number),
        shadow_offset_y: isShadowActive(appearance)
          ? appearance.shadow_offset_y
          : (SHADOW_DEFAULTS.shadow_offset_y as number),
        shadow_color: isShadowActive(appearance)
          ? appearance.shadow_color
          : (SHADOW_DEFAULTS.shadow_color as string),
        shadow_opacity: isShadowActive(appearance)
          ? appearance.shadow_opacity
          : (SHADOW_DEFAULTS.shadow_opacity as number),
        shadow_blur: isShadowActive(appearance)
          ? appearance.shadow_blur
          : (SHADOW_DEFAULTS.shadow_blur as number)
      },
      highlightOpacity
    };
  }

  if (effectId === "background") {
    return {
      appearance: {
        ...baseAppearance,
        background_mode: isBackgroundActive(appearance)
          ? appearance.background_mode
          : "line",
        line_bg_color: appearance.line_bg_color,
        line_bg_opacity: appearance.line_bg_opacity,
        line_bg_padding_top: appearance.line_bg_padding_top,
        line_bg_padding_right: appearance.line_bg_padding_right,
        line_bg_padding_bottom: appearance.line_bg_padding_bottom,
        line_bg_padding_left: appearance.line_bg_padding_left,
        line_bg_radius: appearance.line_bg_radius,
        word_bg_color: appearance.word_bg_color,
        word_bg_opacity: appearance.word_bg_opacity,
        word_bg_padding_top: appearance.word_bg_padding_top,
        word_bg_padding_right: appearance.word_bg_padding_right,
        word_bg_padding_bottom: appearance.word_bg_padding_bottom,
        word_bg_padding_left: appearance.word_bg_padding_left,
        word_bg_radius: appearance.word_bg_radius
      },
      highlightOpacity
    };
  }

  return {
    appearance: {
      ...baseAppearance,
      subtitle_mode: "word_highlight",
      highlight_color: appearance.highlight_color
    },
    highlightOpacity: isKaraokeActive(appearance) ? highlightOpacity : 1
  };
};

const SliderRow = ({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  valueSuffix,
  inputTestId
}: SliderRowProps) => (
  <div className="grid grid-cols-[1fr_auto] items-center gap-3">
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={([nextValue]) => onChange(nextValue)}
      />
    </div>
    <div className="flex items-center gap-1.5">
      <Input
        type="number"
        className="h-8 w-16 px-2 text-xs"
        min={min}
        max={max}
        step={step}
        value={value}
        data-testid={inputTestId}
        onChange={(event) => {
          const nextValue = Number(event.target.value);
          if (!Number.isNaN(nextValue)) {
            onChange(Math.min(max, Math.max(min, nextValue)));
          }
        }}
      />
      {valueSuffix && (
        <span className="text-xs text-muted-foreground">{valueSuffix}</span>
      )}
    </div>
  </div>
);

const OpacityRow = ({
  label,
  value,
  min = 0,
  max = 100,
  onChange,
  inputTestId
}: OpacityRowProps) => (
  <div className="grid grid-cols-[1fr_auto] items-center gap-3">
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <OpacitySlider
        min={min}
        max={max}
        step={1}
        value={[Math.round(value)]}
        onValueChange={([nextValue]) => onChange(nextValue)}
      />
    </div>
    <div className="flex items-center gap-1.5">
      <Input
        type="number"
        className="h-8 w-16 px-2 text-xs"
        min={min}
        max={max}
        step={1}
        value={Math.round(value)}
        data-testid={inputTestId}
        onChange={(event) => {
          const nextValue = Number(event.target.value);
          if (!Number.isNaN(nextValue)) {
            onChange(Math.min(max, Math.max(min, nextValue)));
          }
        }}
      />
      <span className="text-xs text-muted-foreground">%</span>
    </div>
  </div>
);

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
}: PaddingRowProps) => (
  <div className="space-y-1.5">
    <div className="flex items-center justify-between gap-2">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Button
        type="button"
        variant="ghost"
        size="iconSm"
        className="shrink-0"
        onClick={onToggleLink}
        title={linked ? "Unlink padding" : "Link padding"}
        aria-label={linked ? "Unlink padding" : "Link padding"}
      >
        {linked ? <Link className="h-3.5 w-3.5" /> : <Unlink className="h-3.5 w-3.5" />}
      </Button>
    </div>
    {linked ? (
      <div className="grid grid-cols-[1fr_auto] items-center gap-3">
        <Slider
          min={PADDING_MIN}
          max={PADDING_MAX}
          step={PADDING_STEP}
          value={[top]}
          onValueChange={([nextValue]) => onLinkedChange(clampPadding(nextValue))}
        />
        <Input
          type="number"
          className="h-8 w-16 px-2 text-xs"
          min={PADDING_MIN}
          max={PADDING_MAX}
          step={PADDING_STEP}
          value={top}
          onChange={(event) => {
            const nextValue = Number(event.target.value);
            if (!Number.isNaN(nextValue)) {
              onLinkedChange(clampPadding(nextValue));
            }
          }}
        />
      </div>
    ) : (
      <div className="grid grid-cols-4 gap-1.5">
        {[
          { label: "T", value: top, onChange: onTopChange },
          { label: "R", value: right, onChange: onRightChange },
          { label: "B", value: bottom, onChange: onBottomChange },
          { label: "L", value: left, onChange: onLeftChange }
        ].map((item) => (
          <div key={item.label} className="space-y-0.5">
            <Label className="text-[10px] text-muted-foreground">{item.label}</Label>
            <Input
              type="number"
              className="h-8 px-1.5 text-xs"
              min={PADDING_MIN}
              max={PADDING_MAX}
              step={PADDING_STEP}
              value={item.value}
              onChange={(event) => {
                const nextValue = Number(event.target.value);
                if (!Number.isNaN(nextValue)) {
                  item.onChange(clampPadding(nextValue));
                }
              }}
            />
          </div>
        ))}
      </div>
    )}
  </div>
);

const EffectCardPreview = ({
  effectId,
  appearance,
  highlightOpacity
}: {
  effectId: WorkbenchEffectId;
  appearance: SubtitleStyleAppearance;
  highlightOpacity: number;
}) => {
  const preview = buildCardPreviewPayload(effectId, appearance, highlightOpacity);
  const previewAppearance = preview.appearance;
  const linePaddingTop =
    previewAppearance.line_bg_padding_top ?? previewAppearance.line_bg_padding ?? 8;
  const linePaddingRight =
    previewAppearance.line_bg_padding_right ?? previewAppearance.line_bg_padding ?? 8;
  const linePaddingBottom =
    previewAppearance.line_bg_padding_bottom ?? previewAppearance.line_bg_padding ?? 8;
  const linePaddingLeft =
    previewAppearance.line_bg_padding_left ?? previewAppearance.line_bg_padding ?? 8;

  const baseStyle: React.CSSProperties = {
    fontFamily: previewAppearance.font_family || "Heebo",
    fontWeight: previewAppearance.font_weight,
    fontStyle:
      previewAppearance.font_style === "italic" ||
      previewAppearance.font_style === "bold_italic"
        ? "italic"
        : "normal",
    letterSpacing: `${previewAppearance.letter_spacing * 0.5}px`,
    color: colorWithOpacity(
      previewAppearance.text_color,
      previewAppearance.text_opacity
    ),
    textAlign: "center"
  };

  if (effectId === "outline" && previewAppearance.outline_width > 0) {
    baseStyle.textShadow = buildOutlineShadows(
      previewAppearance.outline_color === "auto"
        ? "#000000"
        : previewAppearance.outline_color,
      Math.max(1, previewAppearance.outline_width * 0.55)
    );
  }

  if (effectId === "shadow" && previewAppearance.shadow_strength > 0) {
    baseStyle.textShadow = `${previewAppearance.shadow_offset_x}px ${previewAppearance.shadow_offset_y}px ${Math.max(
      1,
      previewAppearance.shadow_blur * 0.5
    )}px ${colorWithOpacity(
      previewAppearance.shadow_color,
      previewAppearance.shadow_opacity
    )}`;
  }

  if (effectId === "background" && previewAppearance.background_mode === "line") {
    baseStyle.backgroundColor = colorWithOpacity(
      previewAppearance.line_bg_color,
      previewAppearance.line_bg_opacity
    );
    baseStyle.padding = `${Math.max(0, linePaddingTop * 0.4)}px ${Math.max(
      0,
      linePaddingRight * 0.5
    )}px ${Math.max(0, linePaddingBottom * 0.4)}px ${Math.max(
      0,
      linePaddingLeft * 0.5
    )}px`;
    baseStyle.borderRadius = `${Math.max(
      0,
      previewAppearance.line_bg_radius * 0.5
    )}px`;
  }

  const wordHighlightStyle: React.CSSProperties = {
    color: colorWithOpacity(
      previewAppearance.highlight_color,
      preview.highlightOpacity
    )
  };

  if (effectId === "karaoke") {
    return (
      <div className="flex min-h-[4.5rem] w-full items-center justify-center rounded-2xl bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.24),transparent_58%),linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01))] px-3 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
        <div
          className="flex items-center gap-1 text-sm font-semibold tracking-[0.01em]"
          style={baseStyle}
        >
          <span>Cue</span>
          <span className="relative">
            {previewAppearance.background_mode === "word" && (
              <span
                className="absolute inset-0 z-[-1] rounded-md"
                style={{
                  backgroundColor: colorWithOpacity(
                    previewAppearance.word_bg_color,
                    previewAppearance.word_bg_opacity
                  )
                }}
              />
            )}
            <span style={wordHighlightStyle}>Flow</span>
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[4.5rem] w-full items-center justify-center rounded-2xl bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.24),transparent_58%),linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01))] px-3 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
      <span className="text-base font-semibold tracking-[0.01em]" style={baseStyle}>
        {CARD_SAMPLE_TEXT}
      </span>
    </div>
  );
};

const WorkbenchEffectsPanel = ({
  appearance,
  highlightOpacity,
  onAppearanceChange,
  onHighlightOpacityChange,
  onToggleEffect,
  onResetEffect,
  onPreviewEffect
}: WorkbenchEffectsPanelProps) => {
  const [focusedEffect, setFocusedEffect] = React.useState<WorkbenchEffectId | null>(null);
  const activeEffects = React.useMemo(
    () => effectOrder.filter((effectId) => isEffectActive(effectId, appearance)),
    [appearance]
  );
  const resolvedFocusedEffect =
    focusedEffect && isEffectActive(focusedEffect, appearance)
      ? focusedEffect
      : activeEffects[0] ?? null;
  const backgroundMode = appearance.background_mode;
  const karaokeActive = isKaraokeActive(appearance);

  React.useEffect(() => {
    if (!focusedEffect && activeEffects.length > 0) {
      setFocusedEffect(activeEffects[0]);
      return;
    }
    if (focusedEffect && !isEffectActive(focusedEffect, appearance)) {
      setFocusedEffect(activeEffects[0] ?? null);
    }
  }, [activeEffects, appearance, focusedEffect]);

  const patch = (changes: Partial<SubtitleStyleAppearance>) => {
    onAppearanceChange(changes);
  };

  const handleCardClick = (effectId: WorkbenchEffectId) => {
    const isActive = isEffectActive(effectId, appearance);
    if (isActive) {
      if (resolvedFocusedEffect !== effectId) {
        setFocusedEffect(effectId);
        return;
      }
      const remaining = effectOrder.filter(
        (candidate) =>
          candidate !== effectId && isEffectActive(candidate, appearance)
      );
      setFocusedEffect((current) =>
        current === effectId ? remaining[0] ?? null : current
      );
    } else {
      setFocusedEffect(effectId);
    }
    onToggleEffect(effectId);
  };

  const renderFocusedEffectDetail = () => {
    if (!resolvedFocusedEffect) {
      return (
        <div className="rounded-3xl border border-dashed border-border/80 bg-muted/15 px-4 py-8 text-center">
          <p className="text-sm font-medium text-foreground">No active effects</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Click a card to layer an effect onto the subtitle.
          </p>
        </div>
      );
    }

    if (resolvedFocusedEffect === "outline") {
      return (
        <section
          className="space-y-4 rounded-3xl border border-border/80 bg-card/95 p-4 shadow-sm"
          data-testid="workbench-effect-detail-outline"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Outline</p>
              <p className="text-xs text-muted-foreground">
                Tune the edge weight and color for cleaner readability.
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              data-testid="workbench-effect-reset-outline"
              onClick={() => onResetEffect("outline")}
            >
              Reset
            </Button>
          </div>
          <SliderRow
            label="Outline width"
            value={appearance.outline_width}
            min={0}
            max={10}
            step={0.5}
            valueSuffix={appearance.outline_width === 0 ? "Off" : undefined}
            inputTestId="workbench-effect-outline-width-input"
            onChange={(value) =>
              patch({ outline_width: value, outline_enabled: value > 0 })
            }
          />
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Outline color</Label>
            <ColorRow
              kind="outline"
              value={appearance.outline_color}
              onChange={(color) => patch({ outline_color: color })}
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
        </section>
      );
    }

    if (resolvedFocusedEffect === "shadow") {
      return (
        <section
          className="space-y-4 rounded-3xl border border-border/80 bg-card/95 p-4 shadow-sm"
          data-testid="workbench-effect-detail-shadow"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Shadow</p>
              <p className="text-xs text-muted-foreground">
                Add lift with depth, softness, and offset.
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              data-testid="workbench-effect-reset-shadow"
              onClick={() => onResetEffect("shadow")}
            >
              Reset
            </Button>
          </div>
          <SliderRow
            label="Shadow strength"
            value={appearance.shadow_strength}
            min={0}
            max={10}
            step={0.5}
            valueSuffix={appearance.shadow_strength === 0 ? "Off" : undefined}
            onChange={(value) =>
              patch({ shadow_strength: value, shadow_enabled: value > 0 })
            }
          />
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Shadow color</Label>
            <ColorRow
              kind="shadow"
              value={appearance.shadow_color}
              opacity={appearance.shadow_opacity}
              onChange={(color) => patch({ shadow_color: color })}
              onOpacityChange={(opacity) => patch({ shadow_opacity: opacity })}
            />
          </div>
          <OpacityRow
            label="Shadow opacity"
            value={Math.round(appearance.shadow_opacity * 100)}
            min={0}
            max={100}
            inputTestId="workbench-effect-shadow-opacity-input"
            onChange={(value) => patch({ shadow_opacity: value / 100 })}
          />
          <SliderRow
            label="Shadow offset X"
            value={appearance.shadow_offset_x}
            min={-10}
            max={10}
            step={0.5}
            onChange={(value) => patch({ shadow_offset_x: value })}
          />
          <SliderRow
            label="Shadow offset Y"
            value={appearance.shadow_offset_y}
            min={-10}
            max={10}
            step={0.5}
            onChange={(value) => patch({ shadow_offset_y: value })}
          />
          <SliderRow
            label="Shadow blur"
            value={appearance.shadow_blur}
            min={0}
            max={20}
            step={1}
            onChange={(value) => patch({ shadow_blur: value })}
          />
        </section>
      );
    }

    if (resolvedFocusedEffect === "background") {
      const linePaddingTop =
        appearance.line_bg_padding_top ?? appearance.line_bg_padding ?? 8;
      const linePaddingRight =
        appearance.line_bg_padding_right ?? appearance.line_bg_padding ?? 8;
      const linePaddingBottom =
        appearance.line_bg_padding_bottom ?? appearance.line_bg_padding ?? 8;
      const linePaddingLeft =
        appearance.line_bg_padding_left ?? appearance.line_bg_padding ?? 8;
      const wordPaddingTop =
        appearance.word_bg_padding_top ?? appearance.word_bg_padding ?? 8;
      const wordPaddingRight =
        appearance.word_bg_padding_right ?? appearance.word_bg_padding ?? 8;
      const wordPaddingBottom =
        appearance.word_bg_padding_bottom ?? appearance.word_bg_padding ?? 8;
      const wordPaddingLeft =
        appearance.word_bg_padding_left ?? appearance.word_bg_padding ?? 8;

      return (
        <section
          className="space-y-4 rounded-3xl border border-border/80 bg-card/95 p-4 shadow-sm"
          data-testid="workbench-effect-detail-background"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Background</p>
              <p className="text-xs text-muted-foreground">
                Wrap the full line or each highlighted word in a plate.
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              data-testid="workbench-effect-reset-background"
              onClick={() => onResetEffect("background")}
            >
              Reset
            </Button>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Mode</Label>
            <RadioGroup
              value={backgroundMode}
              onValueChange={(value) =>
                patch({ background_mode: value as SubtitleStyleAppearance["background_mode"] })
              }
              className="grid grid-cols-2 gap-2"
            >
              <Label
                htmlFor="workbench-background-line"
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-2xl border px-3 py-2 text-sm transition-colors",
                  backgroundMode === "line"
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border/70 bg-muted/20 text-muted-foreground hover:bg-muted/35"
                )}
              >
                <RadioGroupItem id="workbench-background-line" value="line" />
                Line
              </Label>
              <Label
                htmlFor="workbench-background-word"
                className={cn(
                  "flex items-center gap-2 rounded-2xl border px-3 py-2 text-sm transition-colors",
                  karaokeActive
                    ? "cursor-pointer"
                    : "cursor-not-allowed opacity-60",
                  backgroundMode === "word"
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border/70 bg-muted/20 text-muted-foreground hover:bg-muted/35"
                )}
              >
                <RadioGroupItem
                  id="workbench-background-word"
                  value="word"
                  disabled={!karaokeActive}
                  data-testid="workbench-effect-background-mode-word"
                />
                Word
              </Label>
            </RadioGroup>
            {!karaokeActive && (
              <p className="text-[11px] text-muted-foreground">
                Word backgrounds unlock when Karaoke is active.
              </p>
            )}
          </div>

          {backgroundMode === "line" && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">
                  Background color
                </Label>
                <ColorRow
                  kind="background"
                  value={appearance.line_bg_color}
                  opacity={appearance.line_bg_opacity}
                  onChange={(color) => patch({ line_bg_color: color })}
                  onOpacityChange={(opacity) => patch({ line_bg_opacity: opacity })}
                />
              </div>
              <OpacityRow
                label="Background opacity"
                value={Math.round(appearance.line_bg_opacity * 100)}
                min={0}
                max={100}
                onChange={(value) => patch({ line_bg_opacity: value / 100 })}
              />
              <PaddingRow
                label="Padding"
                top={linePaddingTop}
                right={linePaddingRight}
                bottom={linePaddingBottom}
                left={linePaddingLeft}
                linked={appearance.line_bg_padding_linked ?? true}
                onToggleLink={() => {
                  const linked = appearance.line_bg_padding_linked ?? true;
                  if (linked) {
                    patch({ line_bg_padding_linked: false });
                    return;
                  }
                  patch({
                    line_bg_padding_linked: true,
                    line_bg_padding: linePaddingTop,
                    line_bg_padding_top: linePaddingTop,
                    line_bg_padding_right: linePaddingTop,
                    line_bg_padding_bottom: linePaddingTop,
                    line_bg_padding_left: linePaddingTop
                  });
                }}
                onLinkedChange={(value) =>
                  patch({
                    line_bg_padding: value,
                    line_bg_padding_top: value,
                    line_bg_padding_right: value,
                    line_bg_padding_bottom: value,
                    line_bg_padding_left: value
                  })
                }
                onTopChange={(value) => patch({ line_bg_padding_top: value })}
                onRightChange={(value) => patch({ line_bg_padding_right: value })}
                onBottomChange={(value) => patch({ line_bg_padding_bottom: value })}
                onLeftChange={(value) => patch({ line_bg_padding_left: value })}
              />
              <SliderRow
                label="Corner radius"
                value={appearance.line_bg_radius}
                min={0}
                max={40}
                step={1}
                onChange={(value) => patch({ line_bg_radius: value })}
              />
            </div>
          )}

          {backgroundMode === "word" && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">
                  Background color
                </Label>
                <ColorRow
                  kind="background"
                  value={appearance.word_bg_color}
                  opacity={appearance.word_bg_opacity}
                  onChange={(color) => patch({ word_bg_color: color })}
                  onOpacityChange={(opacity) => patch({ word_bg_opacity: opacity })}
                />
              </div>
              <OpacityRow
                label="Background opacity"
                value={Math.round(appearance.word_bg_opacity * 100)}
                min={0}
                max={100}
                onChange={(value) => patch({ word_bg_opacity: value / 100 })}
              />
              <PaddingRow
                label="Padding"
                top={wordPaddingTop}
                right={wordPaddingRight}
                bottom={wordPaddingBottom}
                left={wordPaddingLeft}
                linked={appearance.word_bg_padding_linked ?? true}
                onToggleLink={() => {
                  const linked = appearance.word_bg_padding_linked ?? true;
                  if (linked) {
                    patch({ word_bg_padding_linked: false });
                    return;
                  }
                  patch({
                    word_bg_padding_linked: true,
                    word_bg_padding: wordPaddingTop,
                    word_bg_padding_top: wordPaddingTop,
                    word_bg_padding_right: wordPaddingTop,
                    word_bg_padding_bottom: wordPaddingTop,
                    word_bg_padding_left: wordPaddingTop
                  });
                }}
                onLinkedChange={(value) =>
                  patch({
                    word_bg_padding: value,
                    word_bg_padding_top: value,
                    word_bg_padding_right: value,
                    word_bg_padding_bottom: value,
                    word_bg_padding_left: value
                  })
                }
                onTopChange={(value) => patch({ word_bg_padding_top: value })}
                onRightChange={(value) => patch({ word_bg_padding_right: value })}
                onBottomChange={(value) => patch({ word_bg_padding_bottom: value })}
                onLeftChange={(value) => patch({ word_bg_padding_left: value })}
              />
              <SliderRow
                label="Corner radius"
                value={appearance.word_bg_radius}
                min={0}
                max={40}
                step={1}
                onChange={(value) => patch({ word_bg_radius: value })}
              />
            </div>
          )}
        </section>
      );
    }

    return (
      <section
        className="space-y-4 rounded-3xl border border-border/80 bg-card/95 p-4 shadow-sm"
        data-testid="workbench-effect-detail-karaoke"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Karaoke</p>
            <p className="text-xs text-muted-foreground">
              Animate the current word with color and opacity.
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            data-testid="workbench-effect-reset-karaoke"
            onClick={() => onResetEffect("karaoke")}
          >
            Reset
          </Button>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-muted-foreground">Highlight color</Label>
          <ColorRow
            kind="highlight"
            value={appearance.highlight_color}
            opacity={highlightOpacity}
            onChange={(color) => patch({ highlight_color: color })}
            onOpacityChange={onHighlightOpacityChange}
          />
        </div>
        <OpacityRow
          label="Highlight opacity"
          value={Math.round(highlightOpacity * 100)}
          min={0}
          max={100}
          inputTestId="workbench-effect-karaoke-opacity-input"
          onChange={(value) => onHighlightOpacityChange(value / 100)}
        />
      </section>
    );
  };

  return (
    <div
      className="space-y-4"
      style={
        {
          "--effects-accent": "hsl(var(--primary))",
          "--effects-muted": "hsl(var(--muted))"
        } as React.CSSProperties
      }
    >
      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Effects</p>
            <p className="text-xs text-muted-foreground">
              Browse looks, hover to preview, click to layer them together.
            </p>
          </div>
          <div className="rounded-full border border-border/70 bg-muted/30 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
            Canva-like
          </div>
        </div>

        <div
          className="grid grid-cols-2 gap-3"
          data-testid="workbench-effects-grid"
        >
          {effectOrder.map((effectId) => {
            const active = isEffectActive(effectId, appearance);
            const focused = resolvedFocusedEffect === effectId;
            return (
              <Button
                key={effectId}
                type="button"
                variant="ghost"
                data-testid={`workbench-effect-card-${effectId}`}
                aria-pressed={active}
                onClick={() => handleCardClick(effectId)}
                onMouseEnter={() => onPreviewEffect(effectId)}
                onMouseLeave={() => onPreviewEffect(null)}
                className={cn(
                  "group relative flex h-auto min-h-[8.5rem] flex-col items-start gap-3 rounded-[1.4rem] border px-3 py-3 text-left transition-all",
                  active
                    ? "border-primary/80 bg-[linear-gradient(180deg,hsl(var(--primary)/0.16),hsl(var(--primary)/0.06))] shadow-[0_0_0_1px_hsl(var(--primary)/0.24),0_14px_28px_-20px_hsl(var(--primary)/0.65)]"
                    : "border-border/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(255,255,255,0.7))] shadow-[0_16px_30px_-26px_rgba(15,23,42,0.45)] hover:border-primary/45 hover:bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.88))]",
                  focused && active && "ring-2 ring-primary/35"
                )}
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {effectId === "karaoke" && (
                      <Sparkles className="h-3.5 w-3.5 text-primary" />
                    )}
                    <span className="text-sm font-semibold text-foreground">
                      {effectLabels[effectId]}
                    </span>
                  </div>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]",
                      active
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted/50 text-muted-foreground"
                    )}
                  >
                    {active ? "On" : "Off"}
                  </span>
                </div>
                <EffectCardPreview
                  effectId={effectId}
                  appearance={appearance}
                  highlightOpacity={highlightOpacity}
                />
                <div className="space-y-0.5">
                  <p className="text-[11px] leading-4 text-muted-foreground">
                    {effectDescriptions[effectId]}
                  </p>
                  <p className="text-[11px] font-medium text-primary/80 opacity-0 transition-opacity group-hover:opacity-100">
                    Hover preview
                  </p>
                </div>
              </Button>
            );
          })}
        </div>
      </section>

      {renderFocusedEffectDetail()}
    </div>
  );
};

export default WorkbenchEffectsPanel;
