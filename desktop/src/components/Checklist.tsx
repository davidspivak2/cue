import * as React from "react";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export type ChecklistState = "pending" | "active" | "done" | "skipped" | "failed";

export type ChecklistItem = {
  id: string;
  label: string;
  state?: ChecklistState;
  detail?: string | null;
};

export type ChecklistProps = {
  items: ChecklistItem[];
} & React.HTMLAttributes<HTMLDivElement>;

const stateIconMap: Record<Exclude<ChecklistState, "skipped">, React.ElementType> = {
  pending: Circle,
  active: Loader2,
  done: CheckCircle2,
  failed: XCircle
};

const stateColorMap: Record<ChecklistState, string> = {
  pending: "text-muted-foreground",
  active: "text-primary",
  done: "text-green-600",
  skipped: "text-muted-foreground",
  failed: "text-destructive"
};

const Checklist = ({ items, className, ...props }: ChecklistProps) => (
  <div className={cn("flex flex-col gap-2.5", className)} {...props}>
    {items.map((item) => {
      const state = item.state ?? "pending";
      const detail = item.detail?.trim();
      const iconClassName = cn(
        "mt-0.5 h-4 w-4 shrink-0",
        state === "active" ? "animate-spin" : "",
        stateColorMap[state]
      );
      return (
        <div
          key={item.id}
          className="flex min-w-0 items-start gap-3"
          data-checklist-item-id={item.id}
          data-checklist-item-state={state}
        >
          {state === "skipped" ? (
            <span
              aria-hidden="true"
              data-checklist-icon-state={state}
              className={cn(iconClassName, "rounded-full border border-dashed border-current")}
            />
          ) : (
            React.createElement(stateIconMap[state], {
              "aria-hidden": "true",
              className: iconClassName,
              "data-checklist-icon-state": state
            })
          )}
          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "break-words text-sm leading-5",
                state === "pending" ? "text-muted-foreground" : "text-foreground"
              )}
            >
              <span>{item.label}</span>
              {detail && (
                <span className="inline">
                  <span className="mx-1 text-muted-foreground" aria-hidden="true">
                    &bull;
                  </span>
                  <span className="break-words text-xs text-muted-foreground">{detail}</span>
                </span>
              )}
            </p>
          </div>
        </div>
      );
    })}
  </div>
);

export default Checklist;
