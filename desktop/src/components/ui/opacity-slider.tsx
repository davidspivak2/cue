import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "@/lib/utils";

const OpacitySlider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn(
      "relative flex w-full cursor-pointer touch-none select-none items-center py-1",
      className
    )}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-3 w-full grow overflow-hidden rounded-full border border-border/50">
      <div
        className="absolute inset-0 rounded-full"
        style={{
          backgroundImage: `
            linear-gradient(90deg, transparent 0%, hsl(var(--primary)) 100%),
            repeating-conic-gradient(#d4d4d4 0% 25%, #fff 25% 50%, #d4d4d4 50% 75%, #fff 75% 100%)
          `,
          backgroundSize: "100% 100%, 8px 8px",
          backgroundPosition: "0 0, 0 0"
        }}
      />
      <SliderPrimitive.Range className="absolute inset-y-0 rounded-full bg-transparent" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="block h-4 w-4 shrink-0 cursor-pointer rounded-full border-2 border-white shadow-md ring-2 ring-black/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&[data-orientation=vertical]]:translate-x-0 [&[data-orientation=vertical]]:translate-y-[-50%] [&[data-orientation=vertical]]:left-1/2 [&[data-orientation=vertical]]:top-[var(--radix-slider-thumb-position)] [&[data-orientation=vertical]]:-translate-x-1/2 [&[data-orientation=horizontal]]:translate-y-[-50%] [&[data-orientation=horizontal]]:left-[var(--radix-slider-thumb-position)] [&[data-orientation=horizontal]]:top-1/2 [&[data-orientation=horizontal]]:-translate-x-1/2 bg-background" />
  </SliderPrimitive.Root>
));
OpacitySlider.displayName = "OpacitySlider";

export { OpacitySlider };
