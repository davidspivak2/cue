import * as React from "react";

import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Check,
  ChevronDown,
  RotateCcw,
  Sparkles
} from "lucide-react";

function FormatLetterSpacingIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      className={className}
      fill="currentColor"
    >
      <path d="M6.7 21.3q-.3.3-.7.3t-.7-.3l-2.6-2.6q-.3-.3-.3-.7t.3-.7l2.6-2.6q.3-.3.7-.3t.7.3t.3.713t-.3.712L5.825 17h12.35l-.875-.875q-.275-.3-.287-.712t.287-.713t.7-.3t.7.3l2.6 2.6q.3.3.3.7t-.3.7l-2.6 2.6q-.3.3-.7.3t-.7-.3t-.3-.712t.3-.713l.875-.875H5.825l.875.875q.275.3.287.713T6.7 21.3m.65-9.5l3.425-9.2q.1-.275.338-.438T11.65 2h.7q.3 0 .538.163t.337.437l3.425 9.225q.15.425-.1.8t-.7.375q-.275 0-.512-.162T15 12.4l-.75-2.2H9.8L9 12.425q-.1.275-.325.425t-.5.15q-.475 0-.737-.387T7.35 11.8m3-3.2h3.3l-1.6-4.55h-.1z" />
    </svg>
  );
}

function OpacityIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      className={className}
      fill="currentColor"
    >
      <path d="M6 6h4v4H6zm4 4h4v4h-4zm4-4h4v4h-4zm8 0h4v4h-4zM6 14h4v4H6zm8 0h4v4h-4zm8 0h4v4h-4zM6 22h4v4H6zm8 0h4v4h-4zm8 0h4v4h-4zm-4-12h4v4h-4zm-8 8h4v4h-4zm8 0h4v4h-4z" />
    </svg>
  );
}

function ItalicSerifIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    >
      <path d="M12 5v14M7 5h10M7 19h10" />
    </svg>
  );
}

import { ColorRow } from "./ColorPopover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { OpacitySlider } from "@/components/ui/opacity-slider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "@/components/ui/popover";
import { Slider } from "@/components/ui/slider";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type {
  SubtitleFontMetadata,
  SubtitleStyleAppearance
} from "@/settingsClient";

type FontOption = SubtitleFontMetadata & { unavailable?: boolean };

const TEXT_APPEARANCE_KEYS: (keyof SubtitleStyleAppearance)[] = [
  "font_family",
  "font_size",
  "font_style",
  "font_weight",
  "text_align",
  "line_spacing",
  "text_color",
  "text_opacity",
  "letter_spacing"
];

function textAppearanceDiffers(
  current: SubtitleStyleAppearance,
  defaultText: Partial<SubtitleStyleAppearance>
): boolean {
  return TEXT_APPEARANCE_KEYS.some(
    (k) => defaultText[k] !== undefined && current[k] !== defaultText[k]
  );
}

type SubtitleTextControlsProps = {
  appearance: SubtitleStyleAppearance;
  fonts: SubtitleFontMetadata[];
  fontsLoading: boolean;
  fontsError: string | null;
  highlightOpacity: number;
  onAppearanceChange: (changes: Partial<SubtitleStyleAppearance>) => void;
  onHighlightOpacityChange: (opacity: number) => void;
  mode?: "panel" | "toolbar";
  showKaraokeControl?: boolean;
  className?: string;
  trailingContent?: React.ReactNode;
  defaultTextAppearance?: Partial<SubtitleStyleAppearance>;
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
const BOLD_WEIGHT_MIN = 700;

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

const FONT_WEIGHT_LABELS: Record<number, string> = {
  100: "Thin",
  200: "Extra Light",
  300: "Light",
  400: "Regular",
  500: "Medium",
  600: "Semi Bold",
  700: "Bold",
  800: "Extra Bold",
  900: "Black"
};

export const getFontWeightLabel = (weight: number): string =>
  FONT_WEIGHT_LABELS[weight] ?? (Number.isInteger(weight) ? `Weight ${weight}` : String(weight));

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
  showKaraokeControl = true,
  className,
  trailingContent,
  defaultTextAppearance
}: SubtitleTextControlsProps) => {
  const [fontOpen, setFontOpen] = React.useState(false);
  const [sizeOpen, setSizeOpen] = React.useState(false);
  const [sizeInputValue, setSizeInputValue] = React.useState(
    String(clampFontSize(appearance.font_size))
  );
  const [karaokeOpen, setKaraokeOpen] = React.useState(false);
  const lastRegularWeightRef = React.useRef<number | null>(null);
  const lastBoldWeightRef = React.useRef<number | null>(null);

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
  const weightOptions = React.useMemo(() => {
    const nextWeights = selectedFont.weights.includes(currentFontWeight)
      ? [...selectedFont.weights]
      : [currentFontWeight, ...selectedFont.weights];
    return Array.from(new Set(nextWeights)).sort((left, right) => left - right);
  }, [currentFontWeight, selectedFont.weights]);
  const isCurrentWeightListed = selectedFont.weights.includes(currentFontWeight);
  const fontControlsDisabled = fontsLoading || Boolean(fontsError);
  const getWeightOptionsForFont = (font: FontOption) => {
    const isSelected = font.family === selectedFont.family;
    if (isSelected && !font.weights.includes(currentFontWeight)) {
      return Array.from(
        new Set([currentFontWeight, ...font.weights])
      ).sort((a, b) => a - b);
    }
    return [...font.weights].sort((a, b) => a - b);
  };
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
          : "Italic isn't available for this font";
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
    } else {
      lastBoldWeightRef.current = currentFontWeight;
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

  const handleFontAndWeightSelect = (
    font: SubtitleFontMetadata,
    weight: number
  ) => {
    patch({
      font_family: font.family,
      font_weight: weight,
      font_style:
        italicActive && font.italic_supported ? "italic" : "regular"
    });
    if (weight < BOLD_WEIGHT_MIN) {
      lastRegularWeightRef.current = weight;
    } else {
      lastBoldWeightRef.current = weight;
    }
    setFontOpen(false);
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
    const nextBoldWeight =
      lastBoldWeightRef.current != null &&
      selectedFont.weights.includes(lastBoldWeightRef.current)
        ? lastBoldWeightRef.current
        : getBoldFallbackWeight(selectedFont.weights);
    patch({ font_weight: nextBoldWeight });
  };

  const isToolbar = mode === "toolbar";
  const hasTextChanges =
    isToolbar &&
    defaultTextAppearance != null &&
    textAppearanceDiffers(appearance, defaultTextAppearance);
  const toolbarShellClass = isToolbar
    ? "flex max-w-[min(90vw,48rem)] flex-nowrap items-center justify-center gap-1.5 rounded-2xl border border-border bg-background/95 px-2 py-1.5 shadow-md backdrop-blur-sm"
    : "flex flex-wrap items-center gap-1.5 rounded-md border border-border/60 bg-muted/20 p-2";
  const toolbarRound = isToolbar ? "rounded-lg" : "rounded-full";

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className={toolbarShellClass}>
        <DropdownMenu
          open={fontOpen}
          onOpenChange={setFontOpen}
        >
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className={cn(
                "h-8 justify-between gap-2 px-3 text-xs font-normal",
                toolbarRound,
                isToolbar ? "min-w-0 max-w-40 shrink" : "min-w-40 max-w-56"
              )}
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
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="min-w-[14rem] w-[min(22rem,var(--radix-dropdown-menu-trigger-width))] p-0"
            align="start"
            onCloseAutoFocus={(e) => e.preventDefault()}
          >
            <div className="max-h-[min(70vh,22rem)] overflow-y-auto p-1">
              {fontOptions.map((font) =>
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
                  ) : font.weights.length <= 1 ? (
                    <DropdownMenuItem
                      key={font.family}
                      onSelect={() =>
                        handleFontAndWeightSelect(
                          font,
                          font.weights[0] ?? font.default_weight
                        )
                      }
                      className="relative flex cursor-pointer items-center rounded-sm py-1.5 pl-8 pr-2 text-xs"
                      style={{ fontFamily: font.family }}
                    >
                      <span className="absolute left-2 flex size-4 items-center justify-center">
                        {font.family === selectedFont.family && (
                          <Check className="size-4" />
                        )}
                      </span>
                      <span className="truncate">{font.family}</span>
                    </DropdownMenuItem>
                  ) : (
                    <DropdownMenuSub key={font.family}>
                      <DropdownMenuSubTrigger
                        className="relative flex cursor-pointer items-center rounded-sm py-1.5 pl-8 pr-2 text-xs"
                        style={{ fontFamily: font.family }}
                      >
                        <span className="absolute left-2 flex size-4 items-center justify-center">
                          {font.family === selectedFont.family && (
                            <Check className="size-4" />
                          )}
                        </span>
                        <span
                          className="min-w-0 flex-1 truncate"
                          onPointerDown={(e) => {
                            if (e.button !== 0) return;
                            e.preventDefault();
                            e.stopPropagation();
                            const regularWeight = getRegularFallbackWeight(
                              font.weights,
                              font.default_weight,
                              lastRegularWeightRef.current
                            );
                            handleFontAndWeightSelect(font, regularWeight);
                            setFontOpen(false);
                          }}
                        >
                          {font.family}
                        </span>
                      </DropdownMenuSubTrigger>
                      <DropdownMenuSubContent className="max-h-[20rem]">
                        {getWeightOptionsForFont(font).map((weight) => {
                          const isCurrent =
                            font.family === selectedFont.family &&
                            weight === currentFontWeight;
                          const showCurrent =
                            isCurrent && !font.weights.includes(currentFontWeight);
                          return (
                            <DropdownMenuItem
                              key={weight}
                              onSelect={() =>
                                handleFontAndWeightSelect(font, weight)
                              }
                              className="relative flex cursor-pointer items-center rounded-sm py-1.5 pl-8 pr-2 text-xs"
                            >
                              <span className="absolute left-2 flex size-4 items-center justify-center">
                                {(isCurrent || showCurrent) && (
                                  <Check className="size-4" />
                                )}
                              </span>
                              {getFontWeightLabel(weight)}
                              {showCurrent ? " (Current)" : ""}
                            </DropdownMenuItem>
                          );
                        })}
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                  )
                )}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        <Button
          type="button"
          variant={boldActive ? "secondary" : "outline"}
          className={cn("h-8 min-w-8 px-2 text-xs font-semibold", toolbarRound)}
          aria-label="Bold"
          aria-pressed={boldActive}
          data-testid="subtitle-style-bold"
          disabled={boldControlDisabled}
          onClick={handleBoldToggle}
        >
          B
        </Button>

        {italicControlDisabled && italicHelperText ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex">
                  <Button
                    type="button"
                    variant={italicActive ? "secondary" : "outline"}
                    className={cn("h-8 min-w-8 px-2 text-xs", toolbarRound)}
                    aria-label="Italic"
                    aria-pressed={italicActive}
                    data-testid="subtitle-style-italic"
                    disabled={italicControlDisabled}
                    onClick={() =>
                      patch({ font_style: italicActive ? "regular" : "italic" })
                    }
                  >
                    <ItalicSerifIcon className="h-4 w-4" />
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>{italicHelperText}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          <Button
            type="button"
            variant={italicActive ? "secondary" : "outline"}
            className={cn("h-8 min-w-8 px-2 text-xs", toolbarRound)}
            aria-label="Italic"
            aria-pressed={italicActive}
            data-testid="subtitle-style-italic"
            disabled={italicControlDisabled}
            onClick={() =>
              patch({ font_style: italicActive ? "regular" : "italic" })
            }
          >
            <ItalicSerifIcon className="h-4 w-4" />
          </Button>
        )}

        <div
          className={cn(
            "flex items-center overflow-hidden border border-input bg-background",
            toolbarRound
          )}
        >
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
          <DropdownMenu
            open={sizeOpen}
            onOpenChange={(open) => {
              setSizeOpen(open);
              if (open) {
                setSizeInputValue(String(clampFontSize(appearance.font_size)));
              }
            }}
          >
            <DropdownMenuTrigger asChild>
              <Input
                type="number"
                min={FONT_SIZE_MIN}
                max={FONT_SIZE_MAX}
                value={sizeInputValue}
                aria-label="Font size"
                data-testid="subtitle-style-font-size-trigger"
                className="h-8 min-w-14 max-w-16 rounded-none border-x border-input bg-background px-2 text-center text-xs [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                onChange={(e) => setSizeInputValue(e.target.value)}
                onBlur={() => commitFontSize(sizeInputValue)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    commitFontSize(sizeInputValue);
                    setSizeOpen(false);
                  }
                }}
              />
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="min-w-0 w-16 p-1"
              align="center"
              onCloseAutoFocus={(e) => e.preventDefault()}
            >
              {FONT_SIZE_PRESETS.map((preset) => (
                <DropdownMenuItem
                  key={preset}
                  className={cn(
                    "cursor-pointer justify-center text-xs",
                    clampFontSize(appearance.font_size) === preset && "bg-accent"
                  )}
                  onSelect={() => {
                    commitFontSize(String(preset));
                    setSizeOpen(false);
                  }}
                >
                  {preset}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
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
              className={cn("h-8 w-8", toolbarRound)}
              aria-label="Text color"
              data-testid="subtitle-style-text-color"
            >
              <span
                className={cn("h-4 w-4 border border-border", isToolbar ? "rounded-md" : "rounded-full")}
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
              className={cn("h-8 w-8", toolbarRound)}
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
              className={cn("h-8 w-8", toolbarRound)}
              aria-label="Spacing"
              data-testid="subtitle-style-spacing"
            >
              <FormatLetterSpacingIcon className="h-4 w-4" />
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
              className={cn("h-8 w-8", toolbarRound)}
              aria-label="Opacity"
              data-testid="subtitle-style-opacity"
            >
              <OpacityIcon className="h-4 w-4" />
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

        {showKaraokeControl && (
          <Popover
            open={isWordHighlight && karaokeOpen}
            onOpenChange={(open) => setKaraokeOpen(open)}
          >
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant={isWordHighlight ? "secondary" : "outline"}
                size="icon"
                className={cn("h-8 w-8", toolbarRound)}
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
        )}

        {trailingContent}
        {hasTextChanges && defaultTextAppearance && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={cn("ml-auto h-8 gap-1.5 px-2 text-xs", toolbarRound)}
            aria-label="Reset text to default"
            data-testid="subtitle-style-reset-text"
            onClick={() => {
              const reset: Partial<SubtitleStyleAppearance> = {};
              for (const k of TEXT_APPEARANCE_KEYS) {
                if (defaultTextAppearance[k] !== undefined) {
                  (reset as Record<string, unknown>)[k] = defaultTextAppearance[k];
                }
              }
              onAppearanceChange(reset);
            }}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </Button>
        )}
      </div>

      {italicHelperText && italicActive && (
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
