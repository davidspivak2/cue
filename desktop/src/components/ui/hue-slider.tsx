import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "@/lib/utils";

export type HueSliderProps = React.ComponentPropsWithoutRef<
  typeof SliderPrimitive.Root
>;

const HUE_GRADIENT =
  "linear-gradient(90deg, #ff0000 0%, #ffff00 17%, #00ff00 33%, #00ffff 50%, #0000ff 67%, #ff00ff 83%, #ff0000 100%)";

const HueSlider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  HueSliderProps
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn(
      "relative flex w-full touch-none select-none items-center",
      className
    )}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-4 w-full grow overflow-hidden rounded-full shadow-[inset_0_0_0_1px_rgba(255,255,255,0.18),inset_0_1px_2px_rgba(15,23,42,0.18)]">
      <div
        className="absolute inset-0 rounded-full"
        style={{ background: HUE_GRADIENT }}
      />
      <SliderPrimitive.Range className="absolute inset-y-0 rounded-full bg-transparent" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="relative z-20 block h-4 w-4 shrink-0 rounded-full border-[3px] border-white bg-transparent shadow-[0_1px_4px_rgba(15,23,42,0.55)] transition-[transform,box-shadow] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50" />
  </SliderPrimitive.Root>
));
HueSlider.displayName = "HueSlider";

export { HueSlider };
