import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * Design system: Buttons
 *
 * Use this component for all actionable buttons. Do not use raw <button> for app actions
 * (exception: highly contextual controls like color swatches). Same semantic = same variant.
 *
 * Variants (choose one per action type):
 * - primary / default: Single main CTA per section (Create subtitles, Export, Add video, Save).
 * - secondary: Supporting actions in a flow (Cancel in flow, Play, Open folder, Browse…, Reset).
 *   Use for label-only and icon+label in the same context; they must share this variant.
 * - tertiary / ghost: Low emphasis (dismiss, back, nav: Cancel in dialogs, Close, Back).
 * - outline: Bordered alternate when you need a distinct border (e.g. Style, view toggle).
 * - overlay: On dark overlays only (e.g. video bar); white text, transparent, white/20 hover.
 * - destructive: Danger actions (Delete, Exit anyway). link: Text link style.
 *
 * Sizes: default (h-9), sm (h-8), lg, icon (h-9×9), iconSm (h-8×8).
 * Icon-only: use size="icon" or size="iconSm" and always set aria-label (and optionally title).
 * Icon + label: put icon and text as children; base gap and [&_svg]:size-4 apply.
 */
const buttonVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary-hover",
        primary: "bg-primary text-primary-foreground shadow hover:bg-primary-hover",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive-hover",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary-hover",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        tertiary: "hover:bg-accent hover:text-accent-foreground",
        overlay:
          "text-white hover:bg-white/20 focus-visible:ring-2 focus-visible:ring-primary [&_svg]:size-5",
        link: "text-primary underline-offset-4 hover:underline"
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
        iconSm: "h-8 w-8"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
