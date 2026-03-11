import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "@/lib/utils";

export interface OpacitySliderProps
  extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> {
  opaqueColor?: string;
}

const OpacitySlider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  OpacitySliderProps
>(({ className, opaqueColor = "hsl(var(--primary))", ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn(
      "relative flex w-full cursor-pointer touch-none select-none items-center",
      className
    )}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-3 w-full grow overflow-hidden rounded-full border border-border/50">
      <div
        className="absolute inset-0 rounded-full"
        style={{
          backgroundImage: `
            linear-gradient(90deg, transparent 0%, ${opaqueColor} 100%),
            repeating-conic-gradient(#d4d4d4 0% 25%, #fff 25% 50%, #d4d4d4 50% 75%, #fff 75% 100%)
          `,
          backgroundSize: "100% 100%, 8px 8px",
          backgroundPosition: "0 0, 0 0"
        }}
      />
      <SliderPrimitive.Range className="absolute inset-y-0 rounded-full bg-transparent" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="relative z-20 block h-4 w-4 shrink-0 cursor-pointer rounded-full border-2 border-white bg-background shadow-md ring-2 ring-black/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50" />
  </SliderPrimitive.Root>
));
OpacitySlider.displayName = "OpacitySlider";

export { OpacitySlider };
