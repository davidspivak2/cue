import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "@/lib/utils";

export interface SliderProps
  extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> {
  stops?: number;
  hideRange?: boolean;
  /** When set, thumb translates outward by this many px at min/max so it aligns with edge labels. */
  thumbEdgeOffset?: number;
}

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  SliderProps
>(({ className, "aria-label": ariaLabel, "aria-describedby": ariaDescribedBy, stops, value, hideRange, thumbEdgeOffset, min = 0, max = 100, ...props }, ref) => {
  const thumbVal = Array.isArray(value) ? value[0] : undefined;
  const atMin = thumbVal !== undefined && thumbVal <= min;
  const atMax = thumbVal !== undefined && thumbVal >= max;
  const thumbStyle =
    thumbEdgeOffset != null
      ? atMin
        ? { transform: `translateX(-${thumbEdgeOffset}px)` }
        : atMax
          ? { transform: `translateX(${thumbEdgeOffset}px)` }
          : undefined
      : undefined;
  return (
  <SliderPrimitive.Root
    ref={ref}
    className={cn(
      "relative flex w-full cursor-pointer touch-none select-none items-center",
      className
    )}
    value={value}
    min={min}
    max={max}
    {...props}
  >
    <SliderPrimitive.Track
      className={cn(
        "relative h-1.5 w-full grow overflow-hidden rounded-full",
        hideRange ? "bg-muted-foreground/25" : "bg-primary/20"
      )}
    >
      <SliderPrimitive.Range
        className={cn("absolute h-full", hideRange ? "bg-transparent" : "bg-primary")}
      />
    </SliderPrimitive.Track>
    {stops != null && stops > 0 ? (
      <div
        className="absolute inset-0 z-10 flex justify-between items-center pointer-events-none px-0"
        aria-hidden
      >
{Array.from({ length: stops }, (_, i) => {
            const thumbIndex = Array.isArray(value) ? value[0] : undefined;
            const isUnderThumb = thumbIndex !== undefined && i === thumbIndex;
            return (
              <div
                key={i}
                className={cn(
                  "h-2 w-2 shrink-0 rounded-full ring-1",
                  "bg-background ring-muted-foreground/50",
                  isUnderThumb && "invisible"
                )}
              />
            );
          })}
      </div>
    ) : null}
    <SliderPrimitive.Thumb
      aria-label={ariaLabel}
      aria-describedby={ariaDescribedBy}
      style={thumbStyle}
      className={cn(
        "relative z-20 block h-4 w-4 cursor-pointer rounded-full bg-background shadow transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
        "border border-primary/50"
      )}
    />
  </SliderPrimitive.Root>
  );
});
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
