import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Toggle as TogglePrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

const toggleVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-md text-sm font-medium disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring outline-none transition-colors duration-200 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive whitespace-nowrap",
  {
    variants: {
      variant: {
        default:
          "bg-transparent hover:bg-muted hover:text-muted-foreground data-[state=on]:bg-secondary data-[state=on]:text-secondary-foreground data-[state=on]:hover:bg-secondary data-[state=on]:hover:text-secondary-foreground",
        outline:
          "border border-input bg-background text-muted-foreground shadow-sm hover:bg-muted hover:text-foreground data-[state=on]:relative data-[state=on]:z-10 data-[state=on]:bg-accent data-[state=on]:font-semibold data-[state=on]:text-[#0f172a] data-[state=on]:after:pointer-events-none data-[state=on]:after:absolute data-[state=on]:after:inset-y-0 data-[state=on]:after:left-0 data-[state=on]:after:w-px data-[state=on]:after:rounded-l-[inherit] data-[state=on]:after:bg-border data-[state=on]:after:content-[''] data-[state=on]:first:after:hidden data-[state=on]:hover:bg-accent data-[state=on]:hover:text-[#0f172a] dark:data-[state=on]:text-foreground dark:data-[state=on]:hover:text-foreground",
      },
      size: {
        default: "h-9 px-2 min-w-9",
        sm: "h-8 px-1.5 min-w-8",
        lg: "h-10 px-2.5 min-w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Toggle({
  className,
  variant,
  size,
  ...props
}: React.ComponentProps<typeof TogglePrimitive.Root> &
  VariantProps<typeof toggleVariants>) {
  return (
    <TogglePrimitive.Root
      data-slot="toggle"
      className={cn(toggleVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Toggle, toggleVariants }
