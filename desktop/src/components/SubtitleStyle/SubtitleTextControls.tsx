import * as React from "react";

import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  ChevronDown,
  Droplets,
  SlidersHorizontal,
  Sparkles
} from "lucide-react";

import { ColorRow } from "./ColorPopover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { OpacitySlider } from "@/components/ui/opacity-slider";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import type {
  SubtitleFontMetadata,
  SubtitleStyleAppearance
} from "@/settingsClient";

type FontOption = SubtitleFontMetadata & { unavailable?: boolean };

type SubtitleTextControlsProps = {
  appearance: SubtitleStyleAppearance;
  fonts: SubtitleFontMetadata[];
  fontsLoading: boolean;
  fontsError: string | null;
  highlightOpacity: number;
  onAppearanceChange: (changes: Partial<SubtitleStyleAppearance>) => void;
  onHighlightOpacityChange: (opacity: number) => void;
  mode?: "panel" | "toolbar";
  className?: string;
  trailingContent?: React.ReactNode;
};

type SliderFieldProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
};

export const DEFAULT_FONT_WEIGHT = 400;
export const FONT_SIZE_MIN = 18;
export const FONT_SIZE_MAX = 72;
const LETTER_SPACING_MIN = -5;
const LETTER_SPACING_MAX = 20;
const LETTER_SPACING_STEP = 0.5;
const LINE_SPACING_MIN = 0.8;
const LINE_SPACING_MAX = 2;
const LINE_SPACING_STEP = 0.05;
const FONT_SIZE_PRESETS = [18, 24, 28, 32, 36, 44, 56, 72];
const BOLD_WEIGHT_MIN = 600;

export const isItalicFontStyle = (fontStyle: string) =>
  fontStyle === "italic" || fontStyle === "bold_italic";

export const normalizeFontWeight = (value: number | undefined) =>
  typeof value === "number" && Number.isFinite(value)
    ? Math.max(100, Math.min(900, Math.round(value)))
    : DEFAULT_FONT_WEIGHT;

export const findFontMetadata = (
  fonts: SubtitleFontMetadata[],
  fontFamily: string
) => {
  const normalized = fontFamily.trim().toLowerCase();
  if (!normalized) return null;
  return (
    fonts.find((font) => font.family.trim().toLowerCase() === normalized) ??
    null
  );
};

const clampFontSize = (value: number) =>
  Math.min(FONT_SIZE_MAX, Math.max(FONT_SIZE_MIN, Math.round(value)));

const clampNumber = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const getBoldFallbackWeight = (weights: number[]) =>
  weights.find((weight) => weight >= 700) ??
  weights.find((weight) => weight >= BOLD_WEIGHT_MIN) ??
  weights[weights.length - 1] ??
  DEFAULT_FONT_WEIGHT;

const getRegularFallbackWeight = (
  weights: number[],
  defaultWeight: number,
  rememberedWeight: number | null
) => {
  if (
    rememberedWeight !== null &&
    rememberedWeight < BOLD_WEIGHT_MIN &&
    weights.includes(rememberedWeight)
  ) {
    return rememberedWeight;
  }
  if (defaultWeight < BOLD_WEIGHT_MIN && weights.includes(defaultWeight)) {
    return defaultWeight;
  }
  const regularWeights = weights.filter((weight) => weight < BOLD_WEIGHT_MIN);
  return regularWeights[regularWeights.length - 1] ?? weights[0] ?? defaultWeight;
};

const sliderInputValue = (value: number, step: number) => {
  if (step >= 1) {
    return String(Math.round(value));
  }
  if (step >= 0.1) {
    return value.toFixed(1);
  }
  return value.toFixed(2);
};

const SliderField = ({
  label,
  value,
  min,
  max,
  step,
  onChange
}: SliderFieldProps) => (
  <div className="space-y-1.5">
    <Label className="text-xs text-muted-foreground">{label}</Label>
    <div className="grid grid-cols-[1fr_auto] items-center gap-3">
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        onValueChange={([nextValue]) => onChange(nextValue)}
      />
      <Input
        type="number"
        className="h-8 w-20 px-2 text-xs"
        min={min}
        max={max}
        step={step}
        value={sliderInputValue(value, step)}
        onChange={(event) => {
          const nextValue = Number(event.target.value);
          if (!Number.isNaN(nextValue)) {
            onChange(clampNumber(nextValue, min, max));
          }
        }}
      />
    </div>
  </div>
);

const getAlignmentIcon = (textAlign: SubtitleStyleAppearance["text_align"]) => {
  if (textAlign === "left") {
    return AlignLeft;
  }
  if (textAlign === "right") {
    return AlignRight;
  }
  return AlignCenter;
};

const SubtitleTextControls = ({
  appearance,
  fonts,
  fontsLoading,
  fontsError,
  highlightOpacity,
  onAppearanceChange,
  onHighlightOpacityChange,
  mode = "panel",
  className,
  trailingContent
}: SubtitleTextControlsProps) => {
  const [fontSearchQuery, setFontSearchQuery] = React.useState("");
  const [fontOpen, setFontOpen] = React.useState(false);
  const [sizeOpen, setSizeOpen] = React.useState(false);
  const [sizeInputValue, setSizeInputValue] = React.useState(
    String(clampFontSize(appearance.font_size))
  );
  const [karaokeOpen, setKaraokeOpen] = React.useState(false);
  const lastRegularWeightRef = React.useRef<number | null>(null);

  const currentFontWeight = React.useMemo(
    () => normalizeFontWeight(appearance.font_weight),
    [appearance.font_weight]
  );
  const italicActive = isItalicFontStyle(appearance.font_style);
  const matchedFont = React.useMemo(
    () => findFontMetadata(fonts, appearance.font_family),
    [appearance.font_family, fonts]
  );
  const selectedFont = React.useMemo<FontOption>(
    () =>
      matchedFont ?? {
        family: appearance.font_family || "Unknown font",
        weights: [currentFontWeight],
        default_weight: currentFontWeight,
        italic_supported: false
      },
    [appearance.font_family, currentFontWeight, matchedFont]
  );
  const isCurrentFontUnavailable =
    !fontsLoading && !fontsError && matchedFont === null;
  const fontOptions = React.useMemo<FontOption[]>(() => {
    const nextOptions = isCurrentFontUnavailable
      ? [{ ...selectedFont, unavailable: true }, ...fonts]
      : [...fonts];
    return nextOptions.filter(
      (font, index, allFonts) =>
        allFonts.findIndex(
          (candidate) =>
            candidate.family.trim().toLowerCase() ===
            font.family.trim().toLowerCase()
        ) === index
    );
  }, [fonts, isCurrentFontUnavailable, selectedFont]);
  const filteredFonts = React.useMemo(() => {
    const normalizedQuery = fontSearchQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return fontOptions;
    }
    return fontOptions.filter((font) =>
      font.family.toLowerCase().includes(normalizedQuery)
    );
  }, [fontOptions, fontSearchQuery]);
  const weightOptions = React.useMemo(() => {
    const nextWeights = selectedFont.weights.includes(currentFontWeight)
      ? [...selectedFont.weights]
      : [currentFontWeight, ...selectedFont.weights];
    return Array.from(new Set(nextWeights)).sort((left, right) => left - right);
  }, [currentFontWeight, selectedFont.weights]);
  const isCurrentWeightListed = selectedFont.weights.includes(currentFontWeight);
  const fontControlsDisabled = fontsLoading || Boolean(fontsError);
  const weightControlDisabled =
    fontControlsDisabled || isCurrentFontUnavailable || weightOptions.length <= 1;
  const boldActive = currentFontWeight >= BOLD_WEIGHT_MIN;
  const hasSupportedBoldWeight =
    selectedFont.weights.some((weight) => weight >= BOLD_WEIGHT_MIN) &&
    selectedFont.weights.length > 0;
  const boldControlDisabled =
    fontControlsDisabled ||
    (isCurrentFontUnavailable ? !boldActive : !hasSupportedBoldWeight);
  const italicControlDisabled =
    fontControlsDisabled || (!selectedFont.italic_supported && !italicActive);
  const fontHelperText = fontsLoading
    ? "Loading bundled font metadata..."
    : fontsError
      ? fontsError
      : isCurrentFontUnavailable
        ? "This saved font is outside the bundled subtitle catalog. Pick a bundled font to edit weight or italic."
        : null;
  const italicHelperText =
    fontsLoading || fontsError
      ? null
      : selectedFont.italic_supported
        ? null
        : italicActive
          ? "Italic is preserved from an older style. You can turn it off, but this font can't be re-enabled."
          : "Italic isn't available for this font.";
  const AlignmentIcon = getAlignmentIcon(appearance.text_align);
  const isWordHighlight = appearance.subtitle_mode === "word_highlight";
  const helperTextClass =
    mode === "toolbar" ? "text-center text-[10px]" : "text-[10px]";

  React.useEffect(() => {
    setSizeInputValue(String(clampFontSize(appearance.font_size)));
  }, [appearance.font_size]);

  React.useEffect(() => {
    if (!boldActive) {
      lastRegularWeightRef.current = currentFontWeight;
    }
  }, [boldActive, currentFontWeight]);

  React.useEffect(() => {
    if (!isWordHighlight) {
      setKaraokeOpen(false);
    }
  }, [isWordHighlight]);

  const patch = (changes: Partial<SubtitleStyleAppearance>) => {
    onAppearanceChange(changes);
  };

  const commitFontSize = (rawValue: string) => {
    const parsed = Number(rawValue);
    const nextValue = clampFontSize(
      Number.isNaN(parsed) ? appearance.font_size : parsed
    );
    patch({ font_size: nextValue });
    setSizeInputValue(String(nextValue));
  };

  const handleFontSizeStep = (delta: number) => {
    commitFontSize(String(appearance.font_size + delta));
  };

  const handleFontSelect = (font: SubtitleFontMetadata) => {
    const nextFontWeight = font.weights.includes(currentFontWeight)
      ? currentFontWeight
      : font.default_weight;
    patch({
      font_family: font.family,
      font_weight: nextFontWeight,
      font_style:
        italicActive && font.italic_supported ? "italic" : "regular"
    });
    if (nextFontWeight < BOLD_WEIGHT_MIN) {
      lastRegularWeightRef.current = nextFontWeight;
    }
    setFontOpen(false);
    setFontSearchQuery("");
  };

  const handleWeightChange = (value: string) => {
    const nextWeight = Number(value);
    if (!Number.isNaN(nextWeight)) {
      patch({ font_weight: nextWeight });
    }
  };

  const handleBoldToggle = () => {
    if (boldControlDisabled) {
      return;
    }
    if (isCurrentFontUnavailable) {
      patch({ font_weight: DEFAULT_FONT_WEIGHT });
      return;
    }
    if (boldActive) {
      const nextWeight = getRegularFallbackWeight(
        selectedFont.weights,
        selectedFont.default_weight,
        lastRegularWeightRef.current
      );
      patch({ font_weight: nextWeight });
      return;
    }
    lastRegularWeightRef.current = currentFontWeight;
    patch({ font_weight: getBoldFallbackWeight(selectedFont.weights) });
  };

  const toolbarShellClass =
    mode === "toolbar"
      ? "flex max-w-[min(90vw,48rem)] flex-wrap items-center justify-center gap-1 rounded-full border border-border/70 bg-background/90 p-1 shadow-lg backdrop-blur-sm"
      : "flex flex-wrap items-center gap-1.5 rounded-md border border-border/60 bg-muted/20 p-2";

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className={toolbarShellClass}>
        <Popover
          open={fontOpen}
          onOpenChange={(open) => {
            setFontOpen(open);
            if (!open) {
              setFontSearchQuery("");
            }
          }}
        >
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className="h-8 min-w-[10rem] max-w-[14rem] justify-between gap-2 rounded-full px-3 text-xs font-normal"
              disabled={fontControlsDisabled}
              aria-label="Font family"
              data-testid="subtitle-style-font-trigger"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span
                  className="truncate"
                  style={
                    isCurrentFontUnavailable
                      ? undefined
                      : { fontFamily: selectedFont.family }
                  }
                >
                  {selectedFont.family}
                </span>
                {isCurrentFontUnavailable && (
                  <span className="shrink-0 rounded-full border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                    Unavailable
                  </span>
                )}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            className="w-[min(22rem,var(--radix-popover-trigger-width))] p-0"
            align="start"
          >
            <Input
              placeholder="Search fonts..."
              className="h-8 rounded-none border-0 border-b focus-visible:ring-0"
              value={fontSearchQuery}
              onChange={(event) => setFontSearchQuery(event.target.value)}
            />
            <ScrollArea className="h-[200px]">
              <div className="p-1">
                {filteredFonts.map((font) =>
                  font.unavailable ? (
                    <div
                      key={font.family}
                      className="flex items-center justify-between rounded-sm px-2 py-1.5 text-xs text-muted-foreground"
                    >
                      <span className="truncate">{font.family}</span>
                      <span className="shrink-0 rounded-full border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em]">
                        Unavailable
                      </span>
                    </div>
                  ) : (
                    <button
                      key={font.family}
                      type="button"
                      data-interactive="true"
                      className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-left text-xs hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground focus:outline-none"
                      style={{ fontFamily: font.family }}
                      onClick={() => handleFontSelect(font)}
                    >
                      <span className="truncate">{font.family}</span>
                      <span className="shrink-0 text-[10px] text-muted-foreground">
                        {font.default_weight}
                      </span>
                    </button>
                  )
                )}
                {filteredFonts.length === 0 && (
                  <div className="py-2 text-center text-xs text-muted-foreground">
                    No matches
                  </div>
                )}
              </div>
            </ScrollArea>
          </PopoverContent>
        </Popover>

        <Select
          value={String(currentFontWeight)}
          onValueChange={handleWeightChange}
          disabled={weightControlDisabled}
        >
          <SelectTrigger
            className="h-8 min-w-[4.75rem] rounded-full px-3 text-xs"
            aria-label="Weight"
            data-testid="subtitle-style-font-weight"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {weightOptions.map((weight) => (
              <SelectItem key={weight} value={String(weight)}>
                {weight === currentFontWeight && !isCurrentWeightListed
                  ? `${weight} (Current)`
                  : String(weight)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          type="button"
          variant={boldActive ? "secondary" : "outline"}
          className="h-8 min-w-8 rounded-full px-2 text-xs font-semibold"
          aria-label="Bold"
          aria-pressed={boldActive}
          data-testid="subtitle-style-bold"
          disabled={boldControlDisabled}
          onClick={handleBoldToggle}
        >
          B
        </Button>

        <Button
          type="button"
          variant={italicActive ? "secondary" : "outline"}
          className="h-8 min-w-8 rounded-full px-2 text-xs italic"
          aria-label="Italic"
          aria-pressed={italicActive}
          data-testid="subtitle-style-italic"
          disabled={italicControlDisabled}
          onClick={() =>
            patch({ font_style: italicActive ? "regular" : "italic" })
          }
        >
          I
        </Button>

        <div className="flex items-center overflow-hidden rounded-full border border-input bg-background">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-none"
            aria-label="Decrease font size"
            data-testid="subtitle-style-font-size-decrease"
            onClick={() => handleFontSizeStep(-1)}
          >
            <span className="text-base leading-none">-</span>
          </Button>
          <Popover
            open={sizeOpen}
            onOpenChange={(open) => {
              setSizeOpen(open);
              if (open) {
                setSizeInputValue(String(clampFontSize(appearance.font_size)));
              }
            }}
          >
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                className="h-8 min-w-[3.5rem] rounded-none border-x px-3 text-xs"
                aria-label="Font size"
                data-testid="subtitle-style-font-size-trigger"
              >
                {clampFontSize(appearance.font_size)}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-56 space-y-3" align="center">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Font size</Label>
                <Input
                  type="number"
                  min={FONT_SIZE_MIN}
                  max={FONT_SIZE_MAX}
                  step={1}
                  value={sizeInputValue}
                  data-testid="subtitle-style-font-size-input"
                  onChange={(event) => setSizeInputValue(event.target.value)}
                  onBlur={() => commitFontSize(sizeInputValue)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      commitFontSize(sizeInputValue);
                      setSizeOpen(false);
                    }
                  }}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Presets</Label>
                <div className="flex flex-wrap gap-1.5">
                  {FONT_SIZE_PRESETS.map((preset) => (
                    <Button
                      key={preset}
                      type="button"
                      size="sm"
                      variant={
                        clampFontSize(appearance.font_size) === preset
                          ? "secondary"
                          : "outline"
                      }
                      className="h-7 rounded-full px-2 text-xs"
                      onClick={() => {
                        commitFontSize(String(preset));
                        setSizeOpen(false);
                      }}
                    >
                      {preset}
                    </Button>
                  ))}
                </div>
              </div>
            </PopoverContent>
          </Popover>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-none"
            aria-label="Increase font size"
            data-testid="subtitle-style-font-size-increase"
            onClick={() => handleFontSizeStep(1)}
          >
            <span className="text-base leading-none">+</span>
          </Button>
        </div>

        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8 rounded-full"
              aria-label="Text color"
              data-testid="subtitle-style-text-color"
            >
              <span
                className="h-4 w-4 rounded-full border border-border"
                style={{
                  backgroundColor: appearance.text_color,
                  opacity: appearance.text_opacity
                }}
              />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 space-y-3" align="center">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Text color</Label>
              <ColorRow
                kind="text"
                value={appearance.text_color}
                onChange={(color) => patch({ text_color: color })}
                opacity={appearance.text_opacity}
                onOpacityChange={(opacity) => patch({ text_opacity: opacity })}
              />
            </div>
          </PopoverContent>
        </Popover>

        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8 rounded-full"
              aria-label="Text alignment"
              data-testid="subtitle-style-alignment"
            >
              <AlignmentIcon className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-44" align="center">
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: "left", label: "Left", Icon: AlignLeft },
                { value: "center", label: "Center", Icon: AlignCenter },
                { value: "right", label: "Right", Icon: AlignRight }
              ].map(({ value, label, Icon }) => (
                <Button
                  key={value}
                  type="button"
                  variant={appearance.text_align === value ? "secondary" : "outline"}
                  className="h-auto flex-col gap-1 rounded-xl px-2 py-2 text-xs"
                  onClick={() =>
                    patch({
                      text_align: value as SubtitleStyleAppearance["text_align"]
                    })
                  }
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Button>
              ))}
            </div>
          </PopoverContent>
        </Popover>

        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8 rounded-full"
              aria-label="Spacing"
              data-testid="subtitle-style-spacing"
            >
              <SlidersHorizontal className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-72 space-y-3" align="center">
            <SliderField
              label="Letter spacing"
              value={appearance.letter_spacing}
              min={LETTER_SPACING_MIN}
              max={LETTER_SPACING_MAX}
              step={LETTER_SPACING_STEP}
              onChange={(value) => patch({ letter_spacing: value })}
            />
            <SliderField
              label="Line spacing"
              value={appearance.line_spacing}
              min={LINE_SPACING_MIN}
              max={LINE_SPACING_MAX}
              step={LINE_SPACING_STEP}
              onChange={(value) => patch({ line_spacing: value })}
            />
          </PopoverContent>
        </Popover>

        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8 rounded-full"
              aria-label="Opacity"
              data-testid="subtitle-style-opacity"
            >
              <Droplets className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-72 space-y-3" align="center">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Text opacity
              </Label>
              <div className="grid grid-cols-[1fr_auto] items-center gap-3">
                <OpacitySlider
                  min={10}
                  max={100}
                  step={1}
                  value={[Math.round(appearance.text_opacity * 100)]}
                  onValueChange={([value]) =>
                    patch({ text_opacity: value / 100 })
                  }
                />
                <Input
                  type="number"
                  className="h-8 w-20 px-2 text-xs"
                  min={10}
                  max={100}
                  step={1}
                  value={Math.round(appearance.text_opacity * 100)}
                  onChange={(event) => {
                    const nextValue = Number(event.target.value);
                    if (!Number.isNaN(nextValue)) {
                      patch({
                        text_opacity: clampNumber(nextValue, 10, 100) / 100
                      });
                    }
                  }}
                />
              </div>
            </div>
          </PopoverContent>
        </Popover>

        <Popover
          open={isWordHighlight && karaokeOpen}
          onOpenChange={(open) => setKaraokeOpen(open)}
        >
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant={isWordHighlight ? "secondary" : "outline"}
              size="icon"
              className="h-8 w-8 rounded-full"
              aria-label="Karaoke"
              aria-pressed={isWordHighlight}
              data-testid="subtitle-style-karaoke"
              onClick={(event) => {
                event.preventDefault();
                if (isWordHighlight) {
                  patch({ subtitle_mode: "static" });
                  setKaraokeOpen(false);
                  return;
                }
                patch({ subtitle_mode: "word_highlight" });
                setKaraokeOpen(true);
              }}
            >
              <Sparkles className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 space-y-3" align="center">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Highlight
              </Label>
              <ColorRow
                kind="highlight"
                value={appearance.highlight_color}
                onChange={(color) => patch({ highlight_color: color })}
                opacity={highlightOpacity}
                onOpacityChange={onHighlightOpacityChange}
              />
            </div>
          </PopoverContent>
        </Popover>

        {trailingContent}
      </div>

      {italicHelperText && (
        <p className={cn(helperTextClass, "text-muted-foreground")}>
          {italicHelperText}
        </p>
      )}
      {fontHelperText && (
        <p
          className={cn(
            helperTextClass,
            fontsError ? "text-destructive" : "text-muted-foreground"
          )}
        >
          {fontHelperText}
        </p>
      )}
      {!fontControlsDisabled && !isCurrentFontUnavailable && !isCurrentWeightListed && (
        <p className={cn(helperTextClass, "text-muted-foreground")}>
          This saved weight is preserved from an older style. Pick a bundled
          weight to normalize it.
        </p>
      )}
    </div>
  );
};

export default SubtitleTextControls;
