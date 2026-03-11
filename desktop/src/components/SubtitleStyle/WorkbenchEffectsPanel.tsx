import * as React from "react";

import { ChevronDown, Link, Unlink } from "lucide-react";

import { ColorRow } from "./ColorPopover";
import {
  clampShadowDistance,
  clampShadowUiAngle,
  DEFAULT_SHADOW_UI_ANGLE_DEGREES,
  shadowOffsetsToUiPolar,
  shadowUiPolarToOffsets
} from "./shadowOffsetUtils";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { OpacitySlider } from "@/components/ui/opacity-slider";
import { Slider } from "@/components/ui/slider";
import { StepperInput } from "@/components/ui/stepper-input";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";
import { useTheme } from "next-themes";
import type { SubtitleStyleAppearance } from "@/settingsClient";

export type WorkbenchEffectId = "outline" | "shadow" | "background" | "karaoke";

type WorkbenchEffectsPanelProps = {
  appearance: SubtitleStyleAppearance;
  highlightOpacity: number;
  isEffectAtDefault: (effectId: WorkbenchEffectId) => boolean;
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
  opaqueColor?: string;
};

type PaddingRowProps = {
  label: string;
  top: number;
  right: number;
  bottom: number;
  left: number;
  previewColor: string;
  previewOpacity: number;
  previewRadius: number;
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
const CARD_SAMPLE_TEXT = "Ag";

const SHADOW_DEFAULTS: Partial<SubtitleStyleAppearance> = {
  shadow_enabled: true,
  shadow_offset_x: 0,
  shadow_offset_y: 0,
  shadow_color: "#000000",
  shadow_opacity: 1,
  shadow_blur: 10
};

const STATIC_CARD_PREVIEW_HIGHLIGHT_OPACITY = 0.8;

const STATIC_CARD_PREVIEW_APPEARANCE: SubtitleStyleAppearance = {
  font_family: "Heebo",
  font_size: 28,
  font_style: "regular",
  font_weight: 400,
  text_align: "center",
  line_spacing: 1.0,
  text_color: "#FFFFFF",
  text_opacity: 1.0,
  letter_spacing: 0,
  outline_enabled: true,
  outline_width: 2,
  outline_color: "#000000",
  shadow_enabled: true,
  shadow_offset_x: 0,
  shadow_offset_y: 0,
  shadow_color: "#000000",
  shadow_opacity: 1,
  shadow_blur: 10,
  background_mode: "line",
  line_bg_color: "#000000",
  line_bg_opacity: 0.7,
  line_bg_padding: 8,
  line_bg_padding_top: 8,
  line_bg_padding_right: 8,
  line_bg_padding_bottom: 8,
  line_bg_padding_left: 8,
  line_bg_padding_linked: true,
  line_bg_radius: 8,
  word_bg_color: "#000000",
  word_bg_opacity: 0.4,
  word_bg_padding: 8,
  word_bg_padding_top: 8,
  word_bg_padding_right: 8,
  word_bg_padding_bottom: 8,
  word_bg_padding_left: 8,
  word_bg_padding_linked: true,
  word_bg_radius: 8,
  vertical_anchor: "bottom",
  vertical_offset: 28,
  position_x: 0.5,
  position_y: 0.92,
  subtitle_mode: "word_highlight",
  highlight_color: "#FFD400"
};

const buildStaticCardPreviewPayload = (
  effectId: WorkbenchEffectId
): CardPreviewPayload =>
  buildCardPreviewPayload(
    effectId,
    STATIC_CARD_PREVIEW_APPEARANCE,
    STATIC_CARD_PREVIEW_HIGHLIGHT_OPACITY
  );

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

const clampPadding = (value: number) =>
  Math.min(PADDING_MAX, Math.max(PADDING_MIN, value));

const isOutlineActive = (appearance: SubtitleStyleAppearance) =>
  appearance.outline_enabled && appearance.outline_width > 0;

const isShadowActive = (appearance: SubtitleStyleAppearance) =>
  appearance.shadow_enabled &&
  (Math.abs(appearance.shadow_offset_x) > 0.1 ||
    Math.abs(appearance.shadow_offset_y) > 0.1 ||
    (appearance.shadow_opacity ?? 0) > 0);

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

const hexToLuminance = (hex: string) => {
  const sanitized = /^#[0-9a-f]{6}$/i.test(hex) ? hex : "#000000";
  const r = Number.parseInt(sanitized.slice(1, 3), 16) / 255;
  const g = Number.parseInt(sanitized.slice(3, 5), 16) / 255;
  const b = Number.parseInt(sanitized.slice(5, 7), 16) / 255;
  const [rs, gs, bs] = [r, g, b].map((c) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  );
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
};

const textColorContrastWith = (fillHex: string) =>
  hexToLuminance(fillHex) > 0.4 ? "#0f172a" : "#fafafa";

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
  <div className="space-y-1.5">
    <Label className="text-xs text-foreground">{label}</Label>
    <div className="grid grid-cols-[1fr_auto] items-center gap-3">
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={([nextValue]) => onChange(nextValue)}
      />
      <div className="flex items-center gap-1.5">
        <StepperInput
          value={value}
          min={min}
          max={max}
          step={step}
          aria-label={label}
          data-testid={inputTestId}
          onChange={onChange}
        />
        {valueSuffix && (
          <span className="text-xs text-muted-foreground">{valueSuffix}</span>
        )}
      </div>
    </div>
  </div>
);

const OpacityRow = ({
  label,
  value,
  min = 0,
  max = 100,
  onChange,
  inputTestId,
  opaqueColor
}: OpacityRowProps) => (
  <div className="space-y-1.5">
    <Label className="text-xs text-foreground">{label}</Label>
    <div className="grid grid-cols-[1fr_auto] items-center gap-3">
      <OpacitySlider
        min={min}
        max={max}
        step={1}
        opaqueColor={opaqueColor}
        value={[Math.round(value)]}
        onValueChange={([nextValue]) => onChange(nextValue)}
      />
      <StepperInput
        value={Math.round(value)}
        min={min}
        max={max}
        step={1}
        aria-label={label}
        data-testid={inputTestId}
        onChange={onChange}
      />
    </div>
  </div>
);

type PaddingSide = "top" | "right" | "bottom" | "left";

const PADDING_PREVIEW_SCALE = 0.75;
const PADDING_PREVIEW_HANDLE_MIN_PX = 10;

const scalePaddingPreview = (value: number) =>
  Math.max(0, Math.min(30, Math.round(value * PADDING_PREVIEW_SCALE)));

const paddingPreviewHandleThickness = (value: number) =>
  Math.max(PADDING_PREVIEW_HANDLE_MIN_PX, scalePaddingPreview(value));

const PaddingPreview = ({
  top,
  right,
  bottom,
  left,
  color,
  opacity,
  radius,
  activeSide,
  onActiveSideChange,
  onSideDragStart
}: {
  top: number;
  right: number;
  bottom: number;
  left: number;
  color: string;
  opacity: number;
  radius: number;
  activeSide: PaddingSide | null;
  onActiveSideChange: (side: PaddingSide | null) => void;
  onSideDragStart: (side: PaddingSide, event: React.PointerEvent<HTMLDivElement>) => void;
}) => {
  const scaledTop = scalePaddingPreview(top);
  const scaledRight = scalePaddingPreview(right);
  const scaledBottom = scalePaddingPreview(bottom);
  const scaledLeft = scalePaddingPreview(left);
  const highlightSize = (value: number) => Math.max(2, value);
  const topHandleHeight = paddingPreviewHandleThickness(top);
  const rightHandleWidth = paddingPreviewHandleThickness(right);
  const bottomHandleHeight = paddingPreviewHandleThickness(bottom);
  const leftHandleWidth = paddingPreviewHandleThickness(left);

  const previewHandle = (
    side: PaddingSide,
    className: string,
    style: React.CSSProperties,
    cursorClassName: string
  ) => (
    <div
      aria-hidden="true"
      className={cn("absolute z-20 touch-none", cursorClassName, className)}
      style={style}
      onPointerEnter={() => onActiveSideChange(side)}
      onPointerLeave={() => onActiveSideChange(null)}
      onPointerDown={(event) => onSideDragStart(side, event)}
    />
  );

  return (
    <div className="flex h-[5.25rem] w-[6.5rem] items-center justify-center rounded-xl border border-border/70 bg-muted/20 p-2 transition-colors">
      <div
        className="relative inline-flex items-center justify-center overflow-hidden shadow-sm transition-all duration-150"
        style={{
          paddingTop: `${scaledTop}px`,
          paddingRight: `${scaledRight}px`,
          paddingBottom: `${scaledBottom}px`,
          paddingLeft: `${scaledLeft}px`,
          borderRadius: `${Math.max(4, Math.round(radius * 0.6))}px`,
          backgroundColor: colorWithOpacity(color, Math.max(opacity, 0.18))
        }}
      >
        {activeSide === "top" && (
          <span
            className="pointer-events-none absolute inset-x-0 top-0 bg-primary/25"
            style={{ height: highlightSize(scaledTop) }}
          />
        )}
        {activeSide === "right" && (
          <span
            className="pointer-events-none absolute right-0 bg-primary/25"
            style={{
              top: scaledTop,
              bottom: scaledBottom,
              width: highlightSize(scaledRight)
            }}
          />
        )}
        {activeSide === "bottom" && (
          <span
            className="pointer-events-none absolute inset-x-0 bottom-0 bg-primary/25"
            style={{ height: highlightSize(scaledBottom) }}
          />
        )}
        {activeSide === "left" && (
          <span
            className="pointer-events-none absolute left-0 bg-primary/25"
            style={{
              top: scaledTop,
              bottom: scaledBottom,
              width: highlightSize(scaledLeft)
            }}
          />
        )}
        {previewHandle(
          "top",
          "inset-x-0 top-0",
          { height: topHandleHeight },
          "cursor-ns-resize!"
        )}
        {previewHandle(
          "right",
          "right-0",
          {
            top: topHandleHeight,
            bottom: bottomHandleHeight,
            width: rightHandleWidth
          },
          "cursor-ew-resize!"
        )}
        {previewHandle(
          "bottom",
          "inset-x-0 bottom-0",
          { height: bottomHandleHeight },
          "cursor-ns-resize!"
        )}
        {previewHandle(
          "left",
          "left-0",
          {
            top: topHandleHeight,
            bottom: bottomHandleHeight,
            width: leftHandleWidth
          },
          "cursor-ew-resize!"
        )}
        <span
          className="relative z-10 text-xs font-semibold tracking-[0.01em]"
          style={{ color: textColorContrastWith(color) }}
        >
          Ag
        </span>
      </div>
    </div>
  );
};

const PaddingSideField = ({
  side,
  value,
  active,
  onChange,
  onActiveChange
}: {
  side: PaddingSide;
  value: number;
  active: boolean;
  onChange: (value: number) => void;
  onActiveChange: (side: PaddingSide | null) => void;
}) => {
  const label = side[0].toUpperCase() + side.slice(1);

  return (
    <div
      className="flex flex-col items-center gap-1"
      onPointerEnter={() => onActiveChange(side)}
      onPointerLeave={() => onActiveChange(null)}
      onFocusCapture={() => onActiveChange(side)}
      onBlurCapture={(event) => {
        const nextFocused = event.relatedTarget;
        if (!(nextFocused instanceof Node) || !event.currentTarget.contains(nextFocused)) {
          onActiveChange(null);
        }
      }}
    >
      <Label
        className={cn(
          "text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground",
          active && "text-foreground"
        )}
      >
        {label}
      </Label>
      <StepperInput
        value={value}
        min={PADDING_MIN}
        max={PADDING_MAX}
        step={PADDING_STEP}
        aria-label={`${label} padding`}
        className={cn(active && "border-primary/40 ring-1 ring-primary/20")}
        inputClassName="w-10 px-1 text-[11px]"
        buttonClassName="w-6"
        onChange={(nextValue) => onChange(clampPadding(nextValue))}
      />
    </div>
  );
};

const PaddingRow = ({
  label,
  top,
  right,
  bottom,
  left,
  previewColor,
  previewOpacity,
  previewRadius,
  linked,
  onToggleLink,
  onLinkedChange,
  onTopChange,
  onRightChange,
  onBottomChange,
  onLeftChange
}: PaddingRowProps) => {
  const [hoveredSide, setHoveredSide] = React.useState<PaddingSide | null>(null);
  const [dragSide, setDragSide] = React.useState<PaddingSide | null>(null);
  const dragStateRef = React.useRef<{
    side: PaddingSide;
    startX: number;
    startY: number;
    startValue: number;
  } | null>(null);
  const activeSide = dragSide ?? hoveredSide;

  const setSideValue = React.useCallback(
    (side: PaddingSide, value: number) => {
      const nextValue = clampPadding(value);
      if (side === "top") {
        onTopChange(nextValue);
        return;
      }
      if (side === "right") {
        onRightChange(nextValue);
        return;
      }
      if (side === "bottom") {
        onBottomChange(nextValue);
        return;
      }
      onLeftChange(nextValue);
    },
    [onBottomChange, onLeftChange, onRightChange, onTopChange]
  );

  const getSideValue = React.useCallback(
    (side: PaddingSide) => {
      if (side === "top") return top;
      if (side === "right") return right;
      if (side === "bottom") return bottom;
      return left;
    },
    [bottom, left, right, top]
  );

  const handleActiveSideChange = React.useCallback((side: PaddingSide | null) => {
    setHoveredSide(side);
  }, []);

  const handleSideDragStart = React.useCallback(
    (side: PaddingSide, event: React.PointerEvent<HTMLDivElement>) => {
      if (event.pointerType === "mouse" && event.button !== 0) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      setHoveredSide(side);
      setDragSide(side);
      dragStateRef.current = {
        side,
        startX: event.clientX,
        startY: event.clientY,
        startValue: getSideValue(side)
      };
    },
    [getSideValue]
  );

  React.useEffect(() => {
    if (!dragSide) {
      return;
    }

    const dragCursor = dragSide === "left" || dragSide === "right"
      ? "ew-resize"
      : "ns-resize";
    const previousUserSelect = document.body.style.userSelect;
    const previousCursor = document.body.style.cursor;
    document.body.style.userSelect = "none";
    document.body.style.cursor = dragCursor;

    const handlePointerMove = (event: PointerEvent) => {
      const drag = dragStateRef.current;
      if (!drag) {
        return;
      }

      const dx = event.clientX - drag.startX;
      const dy = event.clientY - drag.startY;

      let delta = 0;
      if (drag.side === "right") {
        delta = dx / PADDING_PREVIEW_SCALE;
      } else if (drag.side === "left") {
        delta = -dx / PADDING_PREVIEW_SCALE;
      } else if (drag.side === "bottom") {
        delta = dy / PADDING_PREVIEW_SCALE;
      } else {
        delta = -dy / PADDING_PREVIEW_SCALE;
      }

      setSideValue(drag.side, Math.round(drag.startValue + delta));
    };

    const stopDragging = () => {
      dragStateRef.current = null;
      setDragSide(null);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopDragging);
    window.addEventListener("pointercancel", stopDragging);

    return () => {
      document.body.style.userSelect = previousUserSelect;
      document.body.style.cursor = previousCursor;
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopDragging);
      window.removeEventListener("pointercancel", stopDragging);
    };
  }, [dragSide, setSideValue]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-xs text-foreground">{label}</Label>
        <Button
          type="button"
          variant={linked ? "outline" : "secondary"}
          size="sm"
          className="h-7 shrink-0 gap-1.5 px-2 text-xs"
          onClick={onToggleLink}
        >
          {linked ? <Unlink className="h-3.5 w-3.5" /> : <Link className="h-3.5 w-3.5" />}
          {linked ? "Edit individual sides" : "Edit all sides together"}
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
          <StepperInput
            value={top}
            min={PADDING_MIN}
            max={PADDING_MAX}
            step={PADDING_STEP}
            aria-label={label}
            inputClassName="w-12"
            onChange={(nextValue) => onLinkedChange(clampPadding(nextValue))}
          />
        </div>
      ) : (
        <div className="grid grid-cols-[max-content_auto_max-content] grid-rows-[auto_auto_auto] justify-center gap-x-3 gap-y-2">
          <div className="col-start-2 row-start-1 justify-self-center">
            <PaddingSideField
              side="top"
              value={top}
              active={activeSide === "top"}
              onChange={onTopChange}
              onActiveChange={handleActiveSideChange}
            />
          </div>
          <div className="col-start-1 row-start-2 justify-self-end">
            <PaddingSideField
              side="left"
              value={left}
              active={activeSide === "left"}
              onChange={onLeftChange}
              onActiveChange={handleActiveSideChange}
            />
          </div>
          <div className="col-start-2 row-start-2">
            <PaddingPreview
              top={top}
              right={right}
              bottom={bottom}
              left={left}
              color={previewColor}
              opacity={previewOpacity}
              radius={previewRadius}
              activeSide={activeSide}
              onActiveSideChange={handleActiveSideChange}
              onSideDragStart={handleSideDragStart}
            />
          </div>
          <div className="col-start-3 row-start-2 justify-self-start">
            <PaddingSideField
              side="right"
              value={right}
              active={activeSide === "right"}
              onChange={onRightChange}
              onActiveChange={handleActiveSideChange}
            />
          </div>
          <div className="col-start-2 row-start-3 justify-self-center">
            <PaddingSideField
              side="bottom"
              value={bottom}
              active={activeSide === "bottom"}
              onChange={onBottomChange}
              onActiveChange={handleActiveSideChange}
            />
          </div>
        </div>
      )}
    </div>
  );
};

const EffectCardPreview = ({ effectId }: { effectId: WorkbenchEffectId }) => {
  const { resolvedTheme } = useTheme();
  const preview = buildStaticCardPreviewPayload(effectId);
  const previewAppearance = preview.appearance;
  const linePaddingTop =
    previewAppearance.line_bg_padding_top ?? previewAppearance.line_bg_padding ?? 8;
  const linePaddingRight =
    previewAppearance.line_bg_padding_right ?? previewAppearance.line_bg_padding ?? 8;
  const linePaddingBottom =
    previewAppearance.line_bg_padding_bottom ?? previewAppearance.line_bg_padding ?? 8;
  const linePaddingLeft =
    previewAppearance.line_bg_padding_left ?? previewAppearance.line_bg_padding ?? 8;

  const outlineColor =
    previewAppearance.outline_color === "auto"
      ? "#000000"
      : previewAppearance.outline_color;
  const previewTextColor =
    effectId === "background" && resolvedTheme === "light"
      ? "#ffffff"
      : effectId === "outline" && previewAppearance.outline_width > 0
        ? textColorContrastWith(outlineColor)
        : "var(--foreground)";

  const baseStyle: React.CSSProperties = {
    fontFamily: "Heebo",
    fontSize: "2.25rem",
    fontWeight: 600,
    fontStyle: "normal",
    letterSpacing: "0.01em",
    color: previewTextColor,
    textAlign: "center"
  };

  if (effectId === "outline" && previewAppearance.outline_width > 0) {
    baseStyle.textShadow = buildOutlineShadows(
      outlineColor,
      Math.max(1, previewAppearance.outline_width * 0.55)
    );
  }

  if (effectId === "shadow" && isShadowActive(previewAppearance)) {
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

  const previewContainerClassName =
    resolvedTheme === "dark"
      ? "flex min-h-[5.25rem] w-full items-center justify-center rounded-2xl border border-border/50 bg-muted/30 px-3 text-center"
      : "flex min-h-[5.25rem] w-full items-center justify-center rounded-2xl bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.24),transparent_58%),linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01))] px-3 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]";

  if (effectId === "karaoke") {
    return (
      <div
        className={previewContainerClassName}
        data-testid={`workbench-effect-card-${effectId}-preview`}
      >
        <div
          className="flex flex-wrap items-center justify-center gap-x-1.5 text-2xl font-semibold tracking-[0.01em]"
          style={{ ...baseStyle, fontSize: "2.025rem" }}
        >
          <span>This will </span>
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
            <span style={wordHighlightStyle}>highlight</span>
          </span>
          <span> spoken words</span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={previewContainerClassName}
      data-testid={`workbench-effect-card-${effectId}-preview`}
    >
      <span className="text-2xl font-semibold tracking-[0.01em]" style={baseStyle}>
        {CARD_SAMPLE_TEXT}
      </span>
    </div>
  );
};

const WorkbenchEffectsPanel = ({
  appearance,
  highlightOpacity,
  isEffectAtDefault,
  onAppearanceChange,
  onHighlightOpacityChange,
  onToggleEffect,
  onResetEffect,
  onPreviewEffect
}: WorkbenchEffectsPanelProps) => {
  const [focusedEffect, setFocusedEffect] = React.useState<WorkbenchEffectId | null>(null);
  const [expandedEffects, setExpandedEffects] = React.useState<Set<WorkbenchEffectId>>(
    () => new Set()
  );
  const [expandedVisibleEffects, setExpandedVisibleEffects] = React.useState<
    Set<WorkbenchEffectId>
  >(() => new Set());
  const [collapsingEffects, setCollapsingEffects] = React.useState<
    Set<WorkbenchEffectId>
  >(() => new Set());

  const COLLAPSE_DURATION_MS = 200;

  React.useEffect(() => {
    if (collapsingEffects.size === 0) return;
    const id = window.setTimeout(() => {
      setCollapsingEffects(() => new Set());
    }, COLLAPSE_DURATION_MS);
    return () => window.clearTimeout(id);
  }, [collapsingEffects]);

  React.useEffect(() => {
    const toAdd = effectOrder.filter(
      (id) => expandedEffects.has(id) && !expandedVisibleEffects.has(id)
    );
    if (toAdd.length === 0) return;
    const id = requestAnimationFrame(() => {
      setExpandedVisibleEffects((prev) => {
        const next = new Set(prev);
        toAdd.forEach((e) => next.add(e));
        return next;
      });
    });
    return () => cancelAnimationFrame(id);
  }, [expandedEffects, expandedVisibleEffects]);

  const [draftShadowAngle, setDraftShadowAngle] = React.useState(
    DEFAULT_SHADOW_UI_ANGLE_DEGREES
  );
  const activeEffects = React.useMemo(
    () => effectOrder.filter((effectId) => isEffectActive(effectId, appearance)),
    [appearance]
  );
  const resolvedFocusedEffect =
    focusedEffect && isEffectActive(focusedEffect, appearance)
      ? focusedEffect
      : null;
  const shadowPolar = React.useMemo(
    () => shadowOffsetsToUiPolar(appearance.shadow_offset_x, appearance.shadow_offset_y),
    [appearance.shadow_offset_x, appearance.shadow_offset_y]
  );
  const displayedShadowAngle = shadowPolar.hasVisibleOffset
    ? clampShadowUiAngle(shadowPolar.angle)
    : draftShadowAngle;
  const displayedShadowDistance = clampShadowDistance(shadowPolar.distance);
  const backgroundMode = appearance.background_mode;
  const karaokeActive = isKaraokeActive(appearance);

  React.useEffect(() => {
    if (focusedEffect && !isEffectActive(focusedEffect, appearance)) {
      setFocusedEffect(activeEffects[0] ?? null);
    }
  }, [activeEffects, appearance, focusedEffect]);

  React.useEffect(() => {
    if (shadowPolar.hasVisibleOffset) {
      setDraftShadowAngle(clampShadowUiAngle(shadowPolar.angle));
    }
  }, [shadowPolar.angle, shadowPolar.hasVisibleOffset]);

  const patch = (changes: Partial<SubtitleStyleAppearance>) => {
    onAppearanceChange(changes);
  };

  const handleCardClick = (effectId: WorkbenchEffectId) => {
    const isActive = isEffectActive(effectId, appearance);
    if (isActive) {
      if (resolvedFocusedEffect === effectId) {
        const remaining = effectOrder.filter(
          (candidate) =>
            candidate !== effectId && isEffectActive(candidate, appearance)
        );
        setFocusedEffect(remaining[0] ?? null);
      }
      setCollapsingEffects((prev) => new Set(prev).add(effectId));
      setExpandedVisibleEffects((prev) => {
        const next = new Set(prev);
        next.delete(effectId);
        return next;
      });
      setExpandedEffects((prev) => {
        const next = new Set(prev);
        next.delete(effectId);
        return next;
      });
    } else {
      setExpandedEffects((prev) => new Set(prev).add(effectId));
    }
    onToggleEffect(effectId);
  };

  const handleCheckboxChange = (effectId: WorkbenchEffectId) => (
    checked: boolean | "indeterminate"
  ) => {
    if (checked === "indeterminate") return;
    if (checked) {
      onToggleEffect(effectId);
      setExpandedEffects((prev) => new Set(prev).add(effectId));
    } else {
      if (resolvedFocusedEffect === effectId) {
        const remaining = effectOrder.filter(
          (candidate) =>
            candidate !== effectId && isEffectActive(candidate, appearance)
        );
        setFocusedEffect(remaining[0] ?? null);
      }
      setCollapsingEffects((prev) => new Set(prev).add(effectId));
      setExpandedVisibleEffects((prev) => {
        const next = new Set(prev);
        next.delete(effectId);
        return next;
      });
      setExpandedEffects((prev) => {
        const next = new Set(prev);
        next.delete(effectId);
        return next;
      });
      onToggleEffect(effectId);
    }
  };

  const toggleExpanded = (effectId: WorkbenchEffectId) => (e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedEffects((prev) => {
      const next = new Set(prev);
      if (next.has(effectId)) {
        next.delete(effectId);
        setExpandedVisibleEffects((v) => {
          const vNext = new Set(v);
          vNext.delete(effectId);
          return vNext;
        });
      } else {
        next.add(effectId);
      }
      return next;
    });
  };

  const handleShadowAngleChange = (value: number) => {
    const nextAngle = clampShadowUiAngle(value);
    setDraftShadowAngle(nextAngle);
    if (!shadowPolar.hasVisibleOffset) {
      return;
    }
    patch(shadowUiPolarToOffsets(shadowPolar.distance, nextAngle));
  };

  const handleShadowDistanceChange = (value: number) => {
    const nextDistance = clampShadowDistance(value);
    patch(shadowUiPolarToOffsets(nextDistance, displayedShadowAngle));
  };

  const renderEffectControls = (effectId: WorkbenchEffectId) => {
    if (effectId === "outline") {
      return (
        <div className="space-y-4" data-testid="workbench-effect-detail-outline">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-foreground">Color</Label>
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
              hideAutoButton
              compact
            />
          </div>
          <div className="flex items-start justify-between gap-4">
            <div className="grid gap-1.5">
              <Label
                htmlFor="workbench-outline-color-auto"
                className="text-xs text-foreground"
              >
                Color-match to text
              </Label>
              <p className="text-xs text-muted-foreground">
                Automatically adjust outline color so it stays readable on any text color.
              </p>
            </div>
            <Switch
              id="workbench-outline-color-auto"
              checked={appearance.outline_color === "auto"}
              onCheckedChange={(checked) =>
                patch({
                  outline_color: checked
                    ? "auto"
                    : appearance.outline_color === "auto"
                      ? "#000000"
                      : appearance.outline_color
                })
              }
            />
          </div>
          <SliderRow
            label="Width"
            value={appearance.outline_width}
            min={1}
            max={10}
            step={0.5}
            valueSuffix={appearance.outline_width === 0 ? "Off" : undefined}
            inputTestId="workbench-effect-outline-width-input"
            onChange={(value) =>
              patch({ outline_width: value, outline_enabled: value > 0 })
            }
          />
        </div>
      );
    }

    if (effectId === "shadow") {
      return (
        <div className="space-y-4" data-testid="workbench-effect-detail-shadow">
          <div className="space-y-1.5">
            <Label className="text-xs text-foreground">Color</Label>
            <ColorRow
              kind="shadow"
              value={appearance.shadow_color}
              opacity={appearance.shadow_opacity}
              onChange={(color) => patch({ shadow_color: color })}
              onOpacityChange={(opacity) => patch({ shadow_opacity: opacity })}
              compact
            />
          </div>
          <OpacityRow
            label="Opacity"
            value={Math.round(appearance.shadow_opacity * 100)}
            min={0}
            max={100}
            inputTestId="workbench-effect-shadow-opacity-input"
            opaqueColor={appearance.shadow_color}
            onChange={(value) => patch({ shadow_opacity: value / 100 })}
          />
          <SliderRow
            label="Angle"
            value={displayedShadowAngle}
            min={0}
            max={359}
            step={1}
            inputTestId="workbench-effect-shadow-angle-input"
            onChange={handleShadowAngleChange}
          />
          <SliderRow
            label="Distance"
            value={displayedShadowDistance}
            min={0}
            max={15}
            step={0.1}
            inputTestId="workbench-effect-shadow-distance-input"
            onChange={handleShadowDistanceChange}
          />
          <SliderRow
            label="Blur"
            value={appearance.shadow_blur}
            min={0}
            max={20}
            step={1}
            onChange={(value) => patch({ shadow_blur: value })}
          />
        </div>
      );
    }

    if (effectId === "background") {
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
        <div className="space-y-4" data-testid="workbench-effect-detail-background">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-foreground">Mode</Label>
            <ToggleGroup
              type="single"
              variant="outline"
              value={backgroundMode}
              onValueChange={(value) =>
                value && patch({ background_mode: value as SubtitleStyleAppearance["background_mode"] })
              }
              className="inline-flex [&_[data-state=on]]:bg-primary [&_[data-state=on]]:text-primary-foreground [&_[data-state=on]]:border [&_[data-state=on]]:border-primary"
            >
              <ToggleGroupItem value="line" aria-label="Around line">
                Around line
              </ToggleGroupItem>
              <ToggleGroupItem
                value="word"
                aria-label="Around spoken word"
                disabled={!karaokeActive}
                data-testid="workbench-effect-background-mode-word"
              >
                Around spoken word
              </ToggleGroupItem>
            </ToggleGroup>
            {!karaokeActive && (
              <p className="text-[11px] text-muted-foreground">
                Word backgrounds unlock when Karaoke is active.
              </p>
            )}
          </div>

          {backgroundMode === "line" && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs text-foreground">
                  Color
                </Label>
                <ColorRow
                  kind="background"
                  value={appearance.line_bg_color}
                  opacity={appearance.line_bg_opacity}
                  onChange={(color) => patch({ line_bg_color: color })}
                  onOpacityChange={(opacity) => patch({ line_bg_opacity: opacity })}
                  compact
                />
              </div>
              <OpacityRow
                label="Opacity"
                value={Math.round(appearance.line_bg_opacity * 100)}
                min={0}
                max={100}
                opaqueColor={appearance.line_bg_color}
                onChange={(value) => patch({ line_bg_opacity: value / 100 })}
              />
              <PaddingRow
                label="Padding"
                top={linePaddingTop}
                right={linePaddingRight}
                bottom={linePaddingBottom}
                left={linePaddingLeft}
                previewColor={appearance.line_bg_color}
                previewOpacity={appearance.line_bg_opacity}
                previewRadius={appearance.line_bg_radius}
                linked={appearance.line_bg_padding_linked ?? true}
                onToggleLink={() => {
                  const linked = appearance.line_bg_padding_linked ?? true;
                  if (linked) {
                    patch({ line_bg_padding_linked: false });
                    return;
                  }
                  const linkedValue = appearance.line_bg_padding ?? linePaddingTop;
                  patch({
                    line_bg_padding_linked: true,
                    line_bg_padding: linkedValue,
                    line_bg_padding_top: linkedValue,
                    line_bg_padding_right: linkedValue,
                    line_bg_padding_bottom: linkedValue,
                    line_bg_padding_left: linkedValue
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
                label="Corner roundness"
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
                <Label className="text-xs text-foreground">
                  Color
                </Label>
                <ColorRow
                  kind="background"
                  value={appearance.word_bg_color}
                  opacity={appearance.word_bg_opacity}
                  onChange={(color) => patch({ word_bg_color: color })}
                  onOpacityChange={(opacity) => patch({ word_bg_opacity: opacity })}
                  compact
                />
              </div>
              <OpacityRow
                label="Opacity"
                value={Math.round(appearance.word_bg_opacity * 100)}
                min={0}
                max={100}
                opaqueColor={appearance.word_bg_color}
                onChange={(value) => patch({ word_bg_opacity: value / 100 })}
              />
              <PaddingRow
                label="Padding"
                top={wordPaddingTop}
                right={wordPaddingRight}
                bottom={wordPaddingBottom}
                left={wordPaddingLeft}
                previewColor={appearance.word_bg_color}
                previewOpacity={appearance.word_bg_opacity}
                previewRadius={appearance.word_bg_radius}
                linked={appearance.word_bg_padding_linked ?? true}
                onToggleLink={() => {
                  const linked = appearance.word_bg_padding_linked ?? true;
                  if (linked) {
                    patch({ word_bg_padding_linked: false });
                    return;
                  }
                  const linkedValue = appearance.word_bg_padding ?? wordPaddingTop;
                  patch({
                    word_bg_padding_linked: true,
                    word_bg_padding: linkedValue,
                    word_bg_padding_top: linkedValue,
                    word_bg_padding_right: linkedValue,
                    word_bg_padding_bottom: linkedValue,
                    word_bg_padding_left: linkedValue
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
                label="Corner roundness"
                value={appearance.word_bg_radius}
                min={0}
                max={40}
                step={1}
                onChange={(value) => patch({ word_bg_radius: value })}
              />
            </div>
          )}
        </div>
      );
    }

    return (
      <div className="space-y-4" data-testid="workbench-effect-detail-karaoke">
        <div className="space-y-1.5">
          <Label className="text-xs text-foreground">Color</Label>
          <ColorRow
            kind="highlight"
            value={appearance.highlight_color}
            opacity={highlightOpacity}
            onChange={(color) => patch({ highlight_color: color })}
            onOpacityChange={onHighlightOpacityChange}
            compact
          />
        </div>
        <OpacityRow
          label="Opacity"
          value={Math.round(highlightOpacity * 100)}
          min={0}
          max={100}
          inputTestId="workbench-effect-karaoke-opacity-input"
          opaqueColor={appearance.highlight_color}
          onChange={(value) => onHighlightOpacityChange(value / 100)}
        />
      </div>
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
      <section className="space-y-3 pt-4">
        <div
          className="flex flex-col gap-5"
          data-testid="workbench-effects-grid"
        >
          {effectOrder.map((effectId) => {
            const active = isEffectActive(effectId, appearance);
            const focused = resolvedFocusedEffect === effectId;
            const expanded = expandedEffects.has(effectId);
            const expandedVisible = expandedVisibleEffects.has(effectId);
            const isCollapsing = collapsingEffects.has(effectId);
            const showExpandable = active || isCollapsing;
            const showReset = active && !isEffectAtDefault(effectId);
            return (
              <div
                key={effectId}
                data-testid={`workbench-effect-card-${effectId}`}
                onClick={() => handleCardClick(effectId)}
                onMouseEnter={() => onPreviewEffect(effectId)}
                onMouseLeave={() => onPreviewEffect(null)}
                className={cn(
                  "group relative flex min-h-0 flex-col items-stretch gap-4 rounded-lg border border-border bg-card px-4 py-3 text-left shadow-[var(--shadow-card)] transition-colors cursor-pointer",
                  active && "border-primary/50 bg-muted/30",
                  !active && "hover:bg-muted/30",
                  focused && active && "ring-2 ring-primary/20 ring-offset-2 ring-offset-card",
                  !expanded && "pb-6"
                )}
              >
                <div className="flex w-full items-center gap-2 pr-24">
                  <div
                    className="flex shrink-0"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Checkbox
                      checked={active}
                      onCheckedChange={handleCheckboxChange(effectId)}
                      aria-label={`Toggle ${effectLabels[effectId]}`}
                      data-testid={`workbench-effect-card-${effectId}-checkbox`}
                      className="group-hover:bg-muted data-[state=checked]:group-hover:bg-primary/80"
                    />
                  </div>
                  <span className="text-sm font-semibold text-foreground">
                    {effectLabels[effectId]}
                  </span>
                </div>
                {active && (
                  <div className="absolute right-4 top-3 flex shrink-0 items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className={cn(
                        "h-7 px-2 text-xs",
                        !showReset && "invisible pointer-events-none"
                      )}
                      data-testid={`workbench-effect-reset-${effectId}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onResetEffect(effectId);
                      }}
                    >
                      Reset
                    </Button>
                    <button
                      type="button"
                      aria-label={expanded ? "Collapse" : "Expand"}
                      className="-m-2 flex min-h-9 min-w-9 shrink-0 items-center justify-center rounded p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleExpanded(effectId)(e);
                      }}
                    >
                      <ChevronDown
                        className={cn(
                          "h-4 w-4 transition-transform duration-200 ease-out",
                          expanded && "rotate-180"
                        )}
                      />
                    </button>
                  </div>
                )}
                <div className="min-h-[5.25rem]">
                  <EffectCardPreview effectId={effectId} />
                </div>
                {showExpandable && (
                  <div
                    className={cn(
                      "grid transition-[grid-template-rows] duration-200 ease-out",
                      expandedVisible ? "grid-rows-[1fr]" : "grid-rows-[0fr] -mt-3"
                    )}
                  >
                    <div className="min-h-0 overflow-x-visible overflow-y-hidden">
                      <div
                        className="space-y-4 pt-3"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {renderEffectControls(effectId)}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
};

export default WorkbenchEffectsPanel;
